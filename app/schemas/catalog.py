"""
Pydantic v2 schemas — دامنه‌ی پلتفرم نوحه (Artist / Song / Playlist / Auth).

این ماژول جدا از app/schemas/__init__.py (اسکیمای legacyِ Track/Recommender)
است تا تداخل نام رخ ندهد. همه‌ی خروجی‌ها با ConfigDict(from_attributes=True)
مستقیماً از مدل‌های ORM ساخته می‌شوند.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ==================== Artist (مداح) ====================

class ArtistMini(BaseModel):
    """نمای خلاصه‌ی مداح برای تعبیه در Song/Playlist."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cover_url: str | None = None


class ArtistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    bio: str | None = None
    cover_url: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    song_count: int | None = None  # در لیست/جزئیات پر می‌شود


# ==================== Song (نوحه) ====================

class SongResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist_id: int
    audio_url: str
    cover_url: str | None = None
    lyrics: str | None = None
    occasion: str | None = None
    style: str | None = None
    year: int | None = None
    duration: int | None = None
    created_at: datetime
    artist: ArtistMini | None = None


# ==================== Playlist ====================

class PlaylistCreate(BaseModel):
    """بدنه‌ی ساخت پلی‌لیست (فایل کاور جدا و به‌صورت multipart می‌آید)."""
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    is_featured: bool = False
    artist_id: int | None = None


class PlaylistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    cover_url: str | None = None
    is_featured: bool
    artist_id: int | None = None
    created_at: datetime
    song_count: int | None = None


class PlaylistDetailResponse(PlaylistResponse):
    """جزئیات پلی‌لیست همراه با لیست مرتب‌شده‌ی نوحه‌ها."""
    songs: list[SongResponse] = []


class PlaylistAddSongs(BaseModel):
    """افزودن یک یا چند نوحه به پلی‌لیست (به همان ترتیب لیست)."""
    song_ids: list[int] = Field(..., min_length=1)
    start_position: int | None = Field(
        None,
        description="موقعیت شروع؛ اگر خالی باشد، به انتهای پلی‌لیست افزوده می‌شود.",
    )


# ==================== Auth ====================

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: EmailStr | None = None


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None = None
    email: str | None = None
    is_active: bool
    is_admin: bool
    created_at: datetime


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
