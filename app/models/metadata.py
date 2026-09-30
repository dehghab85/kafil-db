"""
مدل‌های متادیتا: Artist (مداح)، Album، Genre.

Artist در پلتفرم کافیل نقشِ «مداح» را دارد و علاوه بر آلبوم/آهنگِ قدیمی،
به نوحه‌ها (Song) و پلی‌لیست‌های گردآوری‌شده (Playlist) نیز مرتبط است.
فیلدهای قبلی (bio, avatar_url, albums, tracks) برای سازگاری کامل حفظ شده‌اند.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.track import Track
    from app.models.song import Song
    from app.models.playlist import Playlist


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True, index=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    # کاور/تصویر شاخصِ مداح (جدا از avatar_url که برای سازگاری با v3 مانده)
    cover_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # --- روابط قدیمی (recommender) ---
    albums: Mapped[list["Album"]] = relationship("Album", back_populates="artist")
    tracks: Mapped[list["Track"]] = relationship("Track", back_populates="artist")

    # --- روابط دامنه‌ی جدید (پلتفرم نوحه) ---
    # حذف مداح → حذف نوحه‌های او (CASCADE در سطح DB و ORM).
    songs: Mapped[list["Song"]] = relationship(
        "Song", back_populates="artist", cascade="all, delete-orphan"
    )
    # حذف مداح → artist_id پلی‌لیست‌ها NULL می‌شود (SET NULL)، پلی‌لیست حذف نمی‌شود.
    playlists: Mapped[list["Playlist"]] = relationship(
        "Playlist", back_populates="artist"
    )

    def __str__(self) -> str:
        """
        نمایش خوانا در پنل ادمین (SQLAdmin).

        SQLAdmin در ستون‌های رابطه‌ای و منوهای انتخابی از ``str(obj)``
        استفاده می‌کند؛ بدون این متد نام کلاس و آدرس حافظه نمایش داده می‌شد
        (مثلاً «<Artist at 0x7f...>» در ستون مداحِ نوحه‌ها).
        """
        return self.name or f"Artist #{self.id}"


class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    release_date = Column(DateTime, nullable=True)
    cover_url = Column(String(500), nullable=True)

    artist: Mapped["Artist"] = relationship("Artist", back_populates="albums")
    tracks: Mapped[list["Track"]] = relationship("Track", back_populates="album")


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)

    tracks: Mapped[list["Track"]] = relationship("Track", secondary="track_genres", back_populates="genres")