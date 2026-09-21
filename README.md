# Kafil Music v4.0 — Spotify-Style Hybrid Recommender

**Production-ready music recommendation engine** with PostgreSQL + pgvector, real-time feedback loop, and FastAPI backend.

---

## 🎵 Features

- **Hybrid Recommendation** — Collaborative Filtering (ALS) + Content-Based (audio features) + Popularity
- **Real-Time Taste Updates** — Instant personalization on every interaction (EMA learning)
- **Cold Start Handling** — Trending tracks for new users, content-only for new tracks
- **PostgreSQL + pgvector** — Native vector storage and ANN search
- **Pure NumPy ML Core** — No heavy dependencies required (upgradeable to sklearn/FAISS/implicit)
- **Admin Dashboard** — SQLAdmin CRUD + custom recommendation debugger (TODO)
- **OTP Authentication** — SMS-based login (Persian-language support)
- **Backward Compatible** — All v3 endpoints preserved

---

## 🚀 Quick Start

```bash
# 1. Clone and install
git clone <repo>
cd kafil-music
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env: set DATABASE_URL and JWT_SECRET_KEY

# 3. Run migrations
./scripts/migrate.sh upgrade

# 4. Create admin user
python create_admin.py

# 5. Run server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. Access
# API Docs: http://localhost:8000/docs
# Admin Panel: http://localhost:8000/admin
```

---

## 📚 Documentation

- **[Setup Guide](docs/SETUP.md)** — Installation, configuration, migration from v3
- **[Architecture](docs/ARCHITECTURE.md)** — ML pipeline deep dive, hybrid scoring
- **[API Reference](docs/API.md)** — Complete endpoint documentation

---

## 🏗️ Architecture

```
User Request → FastAPI Router → Recommendation Service
                                      ↓
                          ┌───────────┴────────────┐
                          │   ML Pipeline          │
                          ├────────────────────────┤
                          │ • ALS (CF)             │
                          │ • Content Embeddings   │
                          │ • ANN Retrieval        │
                          │ • Hybrid Scoring       │
                          └───────────┬────────────┘
                                      ↓
                          PostgreSQL + pgvector
                          • users.taste_vector
                          • tracks.content_vector
                          • user_interactions.weight
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Specific test
pytest tests/test_ml.py -v
```

---

## 🔧 Configuration

All settings via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | sqlite:///./kafil_music.db | DB connection string |
| `JWT_SECRET_KEY` | (required) | JWT signing key |
| `RECO_CF_DIM` | 32 | CF latent dimension |
| `RECO_CONTENT_DIM` | 48 | Content vector dimension |
| `RECO_W_COLLAB` | 0.5 | Hybrid weight: CF |
| `RECO_W_CONTENT` | 0.35 | Hybrid weight: content |
| `RECO_W_POPULARITY` | 0.15 | Hybrid weight: popularity |
| `RECO_REALTIME_LR` | 0.15 | Real-time EMA learning rate |
| `RECO_CF_BACKEND` | numpy | CF backend: numpy/sklearn/implicit |
| `RECO_ANN_BACKEND` | numpy | ANN backend: numpy/pgvector/faiss/annoy |

---

## 🛠️ ML Pipeline

### One-Time Setup

After loading tracks/artists/genres:

```bash
python scripts/run_pipeline.py
```

This computes embeddings, fits CF model, and builds ANN index.

### Scheduled Runs

Production: run nightly for incremental updates.

```bash
# Cron example (3 AM daily)
0 3 * * * cd /path/to/kafil && /path/to/.venv/bin/python scripts/run_pipeline.py
```

### Real-Time Updates

Taste vectors update immediately on each interaction (configurable via `RECO_REALTIME_LR`).

---

## 📊 Performance

- **Training** (10k users, 10k tracks): ~5 seconds (NumPy ALS)
- **Inference** (single recommendation): ~10-20ms (NumPy), <5ms (pgvector/FAISS)
- **Real-time update**: <2ms

---

## 🔄 Migration from v3

1. Export v3 data: `python scripts/export_v3_data.py > v3_data.json`
2. Set up v4 database: `./scripts/migrate.sh upgrade`
3. Import data: `python scripts/import_v3_data.py v3_data.json`
4. Run ML pipeline: `python scripts/run_pipeline.py`

All v3 endpoints remain functional.

---

## 🧹 Code Cleanup

```bash
# Check for unused imports, dead code
python scripts/cleanup_check.py --check

# Auto-fix safe issues (future)
python scripts/cleanup_check.py --fix
```

---

## 📦 Project Structure

```
kafil-music/
├── app/
│   ├── models/          # SQLAlchemy ORM
│   ├── schemas/         # Pydantic models
│   ├── api/routers/     # FastAPI endpoints
│   ├── ml/              # Recommendation engine
│   │   ├── base.py      # Weights, audio features
│   │   ├── collaborative.py  # ALS CF
│   │   ├── retrieval.py # ANN search
│   │   └── pipeline.py  # Orchestration
│   ├── services/        # Business logic
│   ├── security/        # Auth (JWT, OTP)
│   ├── admin/           # SQLAdmin panel
│   ├── config.py        # Settings
│   ├── db.py            # Database session
│   ├── types.py         # Custom column types
│   └── main.py          # FastAPI app
├── alembic/             # Database migrations
├── scripts/             # Helper scripts
├── tests/               # Pytest suite
├── docs/                # Documentation
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Run tests: `pytest`
4. Run linter: `ruff check app/`
5. Submit PR

---

## 📄 License

Proprietary — Kafil Music © 2026

---

## 🔗 Links

- **API Docs:** http://localhost:8000/docs
- **Admin Panel:** http://localhost:8000/admin
- **Setup Guide:** [docs/SETUP.md](docs/SETUP.md)
- **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 📮 Support

For issues, contact the development team or create an issue in the repository.
