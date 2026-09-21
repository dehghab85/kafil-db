"""
مدل‌های ORM (SQLAlchemy) — تمام جداول دیتابیس.

نسخه 4.0 تفاوت‌های کلیدی با نسخه قبل:
  - افزوده شدن ستون‌های برداری (embedding) برای Track و User (pgvector / JSON).
  - Track.audio_features اکنون یک JSON است (tempo, energy, danceability, ...)
  - UserInteraction.context_vector امکان snapshot موقت context کاربر را می‌دهد.
  - Genre/Artist بدون تغییر باقی می‌مانند (backward-compatible).
"""
from app.models.interaction import InteractionType, UserInteraction
from app.models.metadata import Album, Artist, Genre
from app.models.otp import OTPCode
from app.models.playlist import Playlist, playlist_songs
from app.models.song import Song
from app.models.track import Track
from app.models.user import User

__all__ = [
    "User",
    "Track",
    "Song",
    "Artist",
    "Album",
    "Genre",
    "UserInteraction",
    "InteractionType",
    "Playlist",
    "playlist_songs",
    "OTPCode",
]
