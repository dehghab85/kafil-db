"""
Kafil Music API — v4.0 (Spotify-style hybrid recommender).

FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.admin import setup_admin
from app.api.routers import auth, interactions, playlists, recommendations, storage, tracks
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Kafil Music API",
    version="4.0.0",
    description="Spotify-style hybrid music recommendation backend (PostgreSQL + pgvector)",
)

# Session middleware (for admin panel)
app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret_key)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(tracks.router)
app.include_router(interactions.router)
app.include_router(playlists.router)
app.include_router(recommendations.router)
app.include_router(storage.router)

# Admin panel
setup_admin(app)


@app.get("/")
def root():
    return {
        "service": "Kafil Music API",
        "version": "4.0.0",
        "docs": "/docs",
        "admin": "/admin",
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
