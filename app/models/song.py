"""
مدل Song — «نوحه» (محتوای اصلی پلتفرم کافیل).

هر نوحه به یک مداح (Artist) تعلق دارد و می‌تواند در چند پلی‌لیستِ
گردآوری‌شده (Playlist) قرار گیرد. فایل صوتی و کاور روی فضای ابری ParsPack
ذخیره می‌شوند و فقط URL عمومی آن‌ها اینجا نگهداری می‌شود.

این مدل جدا از Track (موتور پیشنهاددهنده‌ی قدیمی) است و با آن تداخل ندارد؛
جدول اختصاصی «songs» دارد.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from app.db import Base
from app.models.playlist import playlist_songs

if TYPE_CHECKING:
    from app.models.metadata import Artist
    from app.models.playlist import Playlist


class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    artist_id = Column(
        Integer,
        ForeignKey("artists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- فایل‌های ذخیره‌شده روی ParsPack (فقط URL عمومی) ---
    audio_url = Column(String(500), nullable=False)
    cover_url = Column(String(500), nullable=True)

    # --- متادیتای مذهبی/محتوایی ---
    lyrics = Column(Text, nullable=True)                 # متن نوحه
    occasion = Column(String(100), nullable=True, index=True)  # مناسبت: محرم، صفر، فاطمیه، رمضان، ...
    style = Column(String(100), nullable=True, index=True)     # سبک: زمینه، واحد، شور، روضه، مدح، ...
    year = Column(Integer, nullable=True, index=True)          # سال انتشار (شمسی یا میلادی)

    duration = Column(Integer, nullable=True)            # مدت (ثانیه)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # --- روابط ---
    artist: Mapped["Artist"] = relationship("Artist", back_populates="songs")
    playlists: Mapped[list["Playlist"]] = relationship(
        "Playlist", secondary=playlist_songs, back_populates="songs"
    )

    def __str__(self) -> str:
        """
        نمایش خوانای نوحه در پنل ادمین (SQLAdmin).

        در لیستهای رابطهای (مثلاً «نوحههای پلیلیست») و منوهای انتخابی،
        SQLAdmin از ``str(obj)`` استفاده میکند؛ با این متد «عنوان — مداح»
        نمایش داده میشود نه نام کلاس و آدرس حافظه.
        """
        artist_name = self.artist.name if self.artist is not None else None
        if artist_name:
            return f"{self.title} — {artist_name}"
        return self.title or f"Song #{self.id}"

    __table_args__ = (
        Index("ix_song_artist_title", "artist_id", "title"),
        Index("ix_song_occasion_style", "occasion", "style"),
    )
