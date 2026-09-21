# ML Architecture Deep Dive

## Hybrid Recommendation System

### 1. Collaborative Filtering (ALS)

**Why ALS?**
- Implicit feedback (plays, likes, skips) → no explicit ratings needed.
- Matrix factorization scales to millions of users/items.
- Pure NumPy implementation stays portable.

**Algorithm:**

Given interaction matrix `R[user, item]` (binary) and confidence matrix `C[user, item]`:

```
Minimize: Σ_{u,i} C[u,i](R[u,i] − x_u · y_i)² + λ(||X||² + ||Y||²)

Where:
  x_u = user latent factor (dim = RECO_CF_DIM)
  y_i = item latent factor
  C[u,i] = 1 + α × |interaction_weight|  (confidence)
  R[u,i] = 1 if user interacted with item, 0 else (preference)
```

**ALS Loop:**
1. Fix `Y` (item factors) → solve for each user `x_u` (ridge regression, closed-form).
2. Fix `X` (user factors) → solve for each item `y_i`.
3. Repeat 15 iterations.

**Implementation:** `app/ml/collaborative.py`

---

### 2. Content-Based Filtering

**Track Embedding Construction:**

```python
track_vector[0:8]   = [danceability, energy, valence, acousticness, 
                       instrumentalness, liveness, speechiness, tempo]
track_vector[8:9]   = [loudness]
track_vector[9:12]  = [genre_1_hot, genre_2_hot, genre_3_hot]
track_vector[12:]   = padding (zeros)
```

All features normalized to [0, 1].

**User Taste Vector:**

```python
taste_vector = Σ_i (weight_i × content_vector_i) / total_weight

where weight_i = interaction_base_weight × time_decay(age)
      time_decay = 0.5 ^ (days_ago / 30)  # 30-day half-life
```

**Implementation:** `app/ml/base.py`, `app/ml/pipeline.py`

---

### 3. Hybrid Scoring

For each candidate track:

```
score = w_collab × cf_score 
      + w_content × content_score 
      + w_popularity × popularity_score

where:
  cf_score = dot(user_cf_vector, item_cf_vector)           ∈ [-1, 1]
  content_score = cosine(taste_vector, content_vector)     ∈ [0, 1]
  popularity_score = normalized(like_count / view_count)   ∈ [0, 1]

  weights: w_collab + w_content + w_popularity = 1.0
```

Weights are configurable per request (admin panel testing) or use defaults from `.env`.

---

### 4. Real-Time Feedback Loop

On every interaction (play, like, skip, complete):

1. **Compute interaction weight:**
   ```python
   weight = base_weight[interaction_type] × time_decay(now)
   ```

2. **Exponential Moving Average (EMA) update:**
   ```python
   new_taste = (1 - lr) × old_taste + lr × weight × track_vector
   new_taste = normalize(new_taste)
   ```
   where `lr = RECO_REALTIME_LR` (default 0.15).

3. **Save to DB:**
   ```python
   user.taste_vector = new_taste.tolist()
   db.commit()
   ```

This allows instant personalization without re-fitting the CF model.

**Implementation:** `app/ml/pipeline.py::RecommendationPipeline.update_user_embedding()`

---

### 5. ANN Retrieval (Candidate Generation)

Given user taste vector, retrieve top-K similar tracks efficiently.

**Backends** (pluggable via `RECO_ANN_BACKEND`):

| Backend | Implementation | Cost | Latency | Notes |
|---------|---|---|---|---|
| **numpy** (default) | Brute-force cosine | O(n) | High | Exact, always works |
| **pgvector** | PostgreSQL `<=>` operator | O(n) | Medium | Native DB, no extra lib |
| **faiss** | IVF / HNSW | O(log n) | Low | GPU-capable, ~95% recall |
| **annoy** | Tree-based | O(log n) | Low | Spotify's choice |

Default uses NumPy (brute-force). For >100k tracks, switch to pgvector or FAISS.

**Implementation:** `app/ml/retrieval.py`

---

### 6. Cold Start Strategies

**New User (no interactions):**
→ Return **trending** tracks (sorted by `like_count + view_count`).

**New Track (no interactions):**
→ Use **content-only** retrieval (ANN on content vector alone).

**Both:**
→ Hybrid content + popularity blend.

---

## Database Schema (v4)

```sql
-- Users with taste vectors
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    phone_number VARCHAR(15) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(128),
    is_admin BOOLEAN DEFAULT FALSE,
    is_phone_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now(),
    
    -- v4 additions
    taste_vector vector(48),          -- pgvector: K-nearest neighbor
    preferred_genre_ids TEXT,          -- JSON array cache
    preferred_artist_ids TEXT          -- JSON array cache
);

-- Tracks with content vectors
CREATE TABLE tracks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    artist_id INTEGER NOT NULL REFERENCES artists(id),
    album_id INTEGER REFERENCES albums(id),
    audio_url VARCHAR(500) NOT NULL,
    cover_url VARCHAR(500),
    duration_sec INTEGER DEFAULT 0,
    release_date TIMESTAMP,
    lyrics TEXT,
    lyrics_timestamps TEXT,          -- JSON
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    skip_count INTEGER DEFAULT 0,
    
    -- v4 additions
    audio_features TEXT,              -- JSON: {tempo, energy, danceability, ...}
    content_vector vector(48)         -- pgvector: content embedding
);

-- Interactions with weights + snapshots
CREATE TABLE user_interactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id INTEGER REFERENCES tracks(id) ON DELETE CASCADE,
    interaction_type ENUM('play', 'complete', 'like', 'unlike', 'skip', 'search'),
    listen_duration INTEGER DEFAULT 0,
    search_query VARCHAR(200),
    timestamp TIMESTAMP DEFAULT now(),
    
    -- v4 additions
    weight FLOAT DEFAULT 0.0,         -- Pre-computed: base_weight × time_decay
    context_vector vector(48)         -- Optional: user's taste_vector at time of interaction
);
CREATE INDEX ix_interaction_user_time ON user_interactions(user_id, timestamp);
```

---

## Configuration Knobs

All configurable via `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `RECO_CONTENT_DIM` | 48 | Dimensionality of content/taste vectors |
| `RECO_CF_DIM` | 32 | Latent dimension for CF model |
| `RECO_W_COLLAB` | 0.5 | Weight of CF in hybrid score |
| `RECO_W_CONTENT` | 0.35 | Weight of content in hybrid score |
| `RECO_W_POPULARITY` | 0.15 | Weight of popularity in hybrid score |
| `RECO_REALTIME_LR` | 0.15 | EMA learning rate for real-time updates |
| `RECO_CANDIDATE_POOL` | 400 | Size of candidate set (before ranking) |
| `RECO_CF_BACKEND` | numpy | CF backend: numpy / sklearn / implicit |
| `RECO_ANN_BACKEND` | numpy | ANN backend: numpy / pgvector / faiss / annoy |
| `RECO_ARTIFACT_DIR` | ./artifacts | Where to save fitted models |

---

## Performance Characteristics

### Training (Full Pipeline Run)

- ~10k users, ~1k tracks: **2-5 seconds** (NumPy ALS, 15 iterations)
- ~100k users, ~100k tracks: **30-120 seconds** (depends on interaction density)

Use `implicit` library for faster CF (GPU acceleration available).

### Inference (Single Recommendation)

- **Retrieval (ANN):** 1-10ms (NumPy brute-force), <1ms (pgvector/FAISS)
- **Scoring & ranking:** <5ms
- **Total latency:** ~10-20ms (NumPy), <5ms (pgvector/FAISS)

---

## Future Enhancements

1. **Audio embeddings** (use pre-trained models like MusicNet).
2. **Contextual bandits** for exploration vs. exploitation.
3. **Graph neural networks** for social recommendations.
4. **Session-based** (temporal dynamics).
5. **Multi-armed bandit** for A/B testing weights.
6. **Distributed training** (Spark / Ray for large-scale).

