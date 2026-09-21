"""
مدل Track (آهنگ) — محتوای اصلی.

علاوه بر متادیتای اساسی (artist, album, genres)، هر آهنگ دارای:
  - content_vector: بردار محتوایی (از audio_features و metadata محاسبه می‌شود).
  - audio_features: ویژگی‌های صوتی به‌صورت JSON (tempo, energy, danceability، ...).
  - lyrics و lyrics_timestamps برای نمایش هماهنگ‌شده‌ی شعر (مانند نسخه قبل).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, relationship

from app.config import get_settings
from app.db import Base
from app.types import EmbeddingType

if TYPE_CHECKING:
    from app.models.metadata import Album, Artist, Genre
    from app.models.user import User
    from app.models.interaction import UserInteraction

settings = get_settings()


# --- Many-to-Many ---

track_genres = Table(
    "track_genres",
    Base.metadata,
    Column("track_id", Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False, index=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True)
    audio_url = Column(String(500), nullable=False)
    cover_url = Column(String(500), nullable=True)
    duration_sec = Column(Integer, default=0)
    release_date = Column(DateTime, nullable=True)

    # --- محتوای شعر (مانند v3) ---
    lyrics = Column(Text, nullable=True)
    lyrics_timestamps = Column(Text, nullable=True)  # JSON array: [{"time":5.2,"text":"..."},...]

    # --- آمار عمومی (برای مرتب‌سازی و cold-start) ---
    view_count = Column(Integer, default=0, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    skip_count = Column(Integer, default=0, nullable=False)

    # --- ویژگی‌های صوتی (Audio features) ---
    # JSON حاوی tempo, energy, danceability, valence, acousticness, loudness، و غیره.
    # این مقادیر یا از یک API (مثل Spotify) می‌آیند یا در backend با librosa استخراج می‌شوند.
    # برای ساخت content_vector به‌کار می‌روند.
    audio_features = Column(Text, nullable=True)  # JSON dict

    # --- بردار محتوایی (Content embedding) ---
    # ترکیبی از ویژگی‌های صوتی و متادیتا (artist, genre, ...).
    content_vector = Column(EmbeddingType(dim=settings.content_dim), nullable=True)

    # --- Relations ---
    artist: Mapped["Artist"] = relationship("Artist", back_populates="tracks")
    album: Mapped[Optional["Album"]] = relationship("Album", back_populates="tracks")
    genres: Mapped[list["Genre"]] = relationship("Genre", secondary=track_genres, back_populates="tracks")
    favorited_by: Mapped[list["User"]] = relationship(
        "User", secondary="user_favorites", back_populates="favorite_tracks"
    )
    interactions: Mapped[list["UserInteraction"]] = relationship(
        "UserInteraction", back_populates="track", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_track_artist_title", "artist_id", "title"),)