"""
Playlist — پلی‌لیستِ گردآوری‌شده (curated) توسط ادمین.

برخلاف نسخه‌ی قبلی (پلی‌لیست شخصیِ کاربر)، در پلتفرم کافیل پلی‌لیست‌ها
مجموعه‌هایی هستند که تیم محتوا می‌سازد؛ مثلاً «برترین نوحه‌های محرم ۱۴۰۳»
یا مجموعه‌ای از یک مداح خاص. هر پلی‌لیست می‌تواند به یک مداح (Artist) نسبت
داده شود (اختیاری) و پرچمِ «ویژه» (is_featured) داشته باشد.

جدول واسط playlist_songs رابطه‌ی چند‌به‌چند با Song را نگه می‌دارد و ترتیب
(position) و زمان افزوده‌شدن (added_at) هر نوحه در پلی‌لیست را ذخیره می‌کند.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.metadata import Artist
    from app.models.song import Song


# --- جدول واسط (junction) پلی‌لیست ↔ نوحه ---
playlist_songs = Table(
    "playlist_songs",
    Base.metadata,
    Column(
        "playlist_id",
        Integer,
        ForeignKey("playlists.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "song_id",
        Integer,
        ForeignKey("songs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("position", Integer, default=0, nullable=False),
    Column(
        "added_at",
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    ),
)


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    cover_url = Column(String(500), nullable=True)
    is_featured = Column(Boolean, default=False, nullable=False, index=True)

    # مداحِ مرتبط (اختیاری). حذف مداح → این فیلد NULL می‌شود.
    artist_id = Column(
        Integer,
        ForeignKey("artists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # --- روابط ---
    artist: Mapped["Artist"] = relationship("Artist", back_populates="playlists")
    songs: Mapped[list["Song"]] = relationship(
        "Song",
        secondary=playlist_songs,
        back_populates="playlists",
        order_by=playlist_songs.c.position,
    )
