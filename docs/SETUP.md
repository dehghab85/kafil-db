# Kafil Music v4.0 — Setup & Migration Guide

**Complete guide to migrate from v3 (SQLite) to v4 (PostgreSQL + pgvector hybrid recommender).**

---

## Overview

Kafil Music v4 is a **production-ready, Spotify-style hybrid music recommendation engine** built on:

- **FastAPI** for the API layer
- **PostgreSQL + pgvector** for vector storage and ANN search
- **Pure NumPy ML core** (upgradeable to scikit-learn/implicit/FAISS)
- **SQLAlchemy 2.0** with Alembic migrations
- **SQLAdmin** for content management
- **Real-time feedback loop** for instant taste vector updates

### Key Features

1. **Hybrid Recommendation** — combines collaborative filtering (ALS matrix factorization), content-based filtering (audio features + metadata embeddings), and popularity scoring.
2. **Cold Start Handling** — new users get trending tracks; new tracks use content-only retrieval.
3. **Real-Time Feedback** — user taste vectors update immediately on each interaction (EMA).
4. **Admin Dashboard** — SQLAdmin CRUD + custom recommendation simulator/debugger.
5. **Backward Compatible** — all v3 `/songs`, `/playlists`, `/interactions` endpoints preserved.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
├─────────────────────────────────────────────────────────────┤
│  Routers: auth, tracks, interactions, playlists, reco       │
│  Security: JWT + OTP                                         │
│  Admin: SQLAdmin + Custom Dashboard                          │
└────────────────┬────────────────────────────────────────────┘
                 │
         ┌───────▼──────────────────────────┐
         │   Recommendation Service          │
         │  (app/services/recommendation.py) │
         └───────┬──────────────────────────┘
                 │
    ┌────────────▼──────────────────┐
    │   ML Pipeline (app/ml/)       │
    ├───────────────────────────────┤
    │  • base.py       — weights    │
    │  • collaborative.py — ALS CF  │
    │  • retrieval.py  — ANN search │
    │  • pipeline.py   — orchestr.  │
    └────────┬──────────────────────┘
             │
    ┌────────▼──────────────────────┐
    │  PostgreSQL + pgvector         │
    │  • users (taste_vector)        │
    │  • tracks (content_vector)     │
    │  • user_interactions (weight)  │
    └────────────────────────────────┘
```

### Recommendation Flow

1. **Candidate Generation (ANN):**  
   User's `taste_vector` → ANN search → top 400 candidate tracks (content-based).

2. **Scoring (Hybrid):**  
   For each candidate:
   - **CF score** = dot(user_cf_vector, item_cf_vector)
   - **Content score** = cosine(taste_vector, content_vector)
   - **Popularity score** = (like_count + 1) / (view_count + 100)
   - **Final** = w_collab × CF + w_content × content + w_pop × popularity

3. **Ranking:**  
   Sort by final score, return top-K.

4. **Real-Time Update (on interaction):**  
   `new_taste = (1 - lr) × old_taste + lr × weight × track_vector`

---

## Prerequisites

- **Python 3.11+** (tested on 3.11, 3.12, 3.14)
- **PostgreSQL 14+** with `pgvector` extension
- **Redis** (optional, for future caching)

---

## Installation

### 1. Clone / Navigate to Project

```bash
cd D:/Kafil  # or your project root
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

# Optional: heavier ML backends (scikit-learn, FAISS, Annoy)
pip install -r requirements-ml.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

**Example `.env` for development (SQLite):**

```env
JWT_SECRET_KEY=your_random_hex_here
DATABASE_URL=sqlite:///./kafil_music.db
RECO_CF_BACKEND=numpy
RECO_ANN_BACKEND=numpy
```

**Example `.env` for production (PostgreSQL + pgvector):**

```env
JWT_SECRET_KEY=your_random_hex_here
DATABASE_URL=postgresql+psycopg2://kafil:kafil@localhost:5432/kafil_music
RECO_CF_BACKEND=numpy
RECO_ANN_BACKEND=pgvector
CORS_ORIGINS=https://yourdomain.com
```

Generate a secure secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Set Up PostgreSQL (Production)

```sql
CREATE DATABASE kafil_music;
CREATE USER kafil WITH PASSWORD 'kafil';
GRANT ALL PRIVILEGES ON DATABASE kafil_music TO kafil;

-- Enable pgvector extension
\c kafil_music
CREATE EXTENSION IF NOT EXISTS vector;
```

### 6. Run Migrations

```bash
# Apply all migrations (creates tables + pgvector extension)
./scripts/migrate.sh upgrade

# Or use Alembic directly:
alembic upgrade head
```

### 7. Create Admin User

```bash
python create_admin.py
```

Enter username, email, phone, and password when prompted.

---

## Running the Application

### Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use Docker:

```bash
docker build -t kafil-music .
docker run -p 8000:80 --env-file .env kafil-music
```

### Access Points

- **API Docs (Swagger):** http://localhost:8000/docs
- **Admin Panel:** http://localhost:8000/admin
- **Health Check:** http://localhost:8000/health

---

## ML Pipeline

### First-Time Setup

After loading tracks, artists, genres into the database:

```bash
# Trigger full pipeline rebuild
python scripts/run_pipeline.py
```

This will:
1. Compute `content_vector` for all tracks (from `audio_features` + metadata).
2. Fit collaborative filtering model (ALS) on interaction history.
3. Build ANN index for fast retrieval.
4. Compute `taste_vector` for all users with interactions.

Artifacts are saved to `./artifacts/` (configurable via `RECO_ARTIFACT_DIR`).

### Scheduled / Periodic Runs

In production, run the pipeline:
- **Daily** (off-peak hours) for incremental updates.
- **Weekly** for full rebuilds.

Use a cron job or orchestrator:

```bash
0 3 * * * cd /path/to/kafil && /path/to/.venv/bin/python scripts/run_pipeline.py
```

### Manual Trigger (Admin Panel)

Admins can trigger pipeline runs via:

```
POST /recommendations/pipeline/run
```

(Requires admin JWT token.)

---

## API Usage

### Authentication (OTP)

```bash
# 1. Request OTP
curl -X POST http://localhost:8000/auth/otp/request \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "09123456789"}'

# 2. Verify OTP (receive JWT)
curl -X POST http://localhost:8000/auth/otp/verify \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "09123456789", "code": "123456"}'

# Response: {"access_token": "...", "token_type": "bearer", "user": {...}}
```

### Get Personalized Recommendations

```bash
curl -X GET http://localhost:8000/playlists/recommended?limit=30 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Log Interaction (Real-Time Feedback)

```bash
curl -X POST http://localhost:8000/interactions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "track_id": 123,
    "interaction_type": "like",
    "listen_duration": 0
  }'
```

Interaction types: `play`, `complete`, `like`, `unlike`, `skip`, `search`.

---

## Admin Dashboard

### SQLAdmin (CRUD)

Navigate to http://localhost:8000/admin and log in with admin credentials.

You can:
- Browse/edit users, tracks, artists, albums, genres, playlists, interactions.
- View interaction history and statistics.

### Custom Recommendation Debugger (TODO)

A custom HTML dashboard will be added at `/admin/recommender` with:
- **Pipeline Control:** Trigger full rebuild, view status.
- **User Profiler:** Inspect taste vector, top genres/artists, recent interactions.
- **Recommendation Simulator:** Test recommendations with custom weights.
- **Feedback Simulator:** Send fake interactions, observe taste vector updates.

---

## Migration from v3 (SQLite)

### Data Migration Path

1. **Export v3 data:**

```bash
# Dump SQLite to JSON
python scripts/export_v3_data.py > v3_data.json
```

2. **Set up v4 PostgreSQL database** (see Installation above).

3. **Import data:**

```bash
python scripts/import_v3_data.py v3_data.json
```

4. **Run ML pipeline:**

```bash
python scripts/run_pipeline.py
```

### Endpoint Compatibility

All v3 endpoints are preserved:

| v3 Path | v4 Path | Status |
|---------|---------|--------|
| `POST /users/register` | ✓ Same | Backward compatible |
| `POST /login` | ✓ Same | Backward compatible |
| `GET /songs` | ✓ Same (aliased to `/tracks`) | Compatible |
| `POST /interactions` | ✓ Same | Compatible |
| `GET /playlists/recommended` | ✓ **Upgraded** (now uses v4 ML) | Compatible |

Your Flutter client should work without changes.

---

## Troubleshooting

### "Module not found" errors

Ensure you're in the virtual environment:

```bash
source .venv/bin/activate
```

### pgvector extension missing

```sql
\c kafil_music
CREATE EXTENSION vector;
```

### Pipeline fails with empty interactions

The CF model requires at least one interaction. Add seed data:

```bash
python scripts/seed_data.py
```

### Real-time feedback not updating

Check `RECO_REALTIME_LR` in `.env` — must be > 0 (default 0.15).

---

## Next Steps

- [ ] Add custom HTML admin dashboard (`app/admin/templates/`).
- [ ] Implement pgvector ANN backend (`app/ml/retrieval.py`).
- [ ] Add audio feature extraction (librosa integration).
- [ ] Add Redis caching for hot recommendations.
- [ ] Add A/B testing framework.
- [ ] Add monitoring (Prometheus + Grafana).

---

## License

Proprietary — Kafil Music © 2026
