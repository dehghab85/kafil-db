"""
Pydantic schemas — ساختارهای JSON برای API.

این schemas بیشتر سازگار با نسخه v3.0 هستند تا endpoint های موجود بدون شکست کار کنند.
تنها تفاوت‌ها: Song → Track و schemas جدید برای recommender admin panel.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ==================== Auth ====================

class OTPRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)


class OTPVerify(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)
    code: str = Field(..., min_length=6, max_length=6)


class UserSetCredentials(BaseModel):
    """مرحله دوم ثبت‌نام."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: EmailStr | None = None


class UserCreate(BaseModel):
    """ثبت‌نام کلاسیک. phone_number و email اختیاری‌اند (username/password کافی است)."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    phone_number: str | None = Field(None, min_length=8, max_length=15)
    email: EmailStr | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None = None
    phone_number: str | None = None
    email: str | None = None
    is_active: bool = True
    is_phone_verified: bool
    created_at: datetime
    preferred_genre_ids: str | None = None
    preferred_artist_ids: str | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ==================== Metadata ====================

class ArtistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    avatar_url: str | None = None


class AlbumOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cover_url: str | None = None
    release_date: datetime | None = None


class GenreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# ==================== Track (Song) ====================

class TrackOut(BaseModel):
    """
    مانند SongOut نسخه قبل، فقط نام تغییر کرد.
    برای سازگاری، endpoint /songs همچنان این schema را برمی‌گرداند.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    audio_url: str
    cover_url: str | None = None
    duration_sec: int
    lyrics: str | None = None
    lyrics_timestamps: str | None = None
    view_count: int
    like_count: int
    artist: ArtistOut
    album: AlbumOut | None = None
    genres: list[GenreOut] = []


# Alias برای سازگاری
SongOut = TrackOut


class TrackCreate(BaseModel):
    title: str
    artist_id: int
    album_id: int | None = None
    audio_url: str
    cover_url: str | None = None
    duration_sec: int = 0
    lyrics: str | None = None
    lyrics_timestamps: str | None = None
    genre_ids: list[int] = []
    audio_features: dict | None = None  # JSON: {tempo: 120, energy: 0.8, ...}


SongCreate = TrackCreate


# ==================== Interaction ====================

class InteractionCreate(BaseModel):
    track_id: int | None = None
    interaction_type: str
    listen_duration: int = 0
    search_query: str | None = None


class InteractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int | None
    interaction_type: str
    listen_duration: int
    timestamp: datetime


# ==================== Playlist ====================

class PlaylistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    is_private: bool = True


class PlaylistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_private: bool
    is_auto_generated: bool
    created_at: datetime
    tracks: list[TrackOut] = []


class PlaylistAddTrack(BaseModel):
    track_id: int


# Alias سازگاری
PlaylistAddSong = PlaylistAddTrack


# ==================== Recommender (Admin/Debug) ====================

class RecommendationRequest(BaseModel):
    """درخواست پیشنهاد آهنگ (با پارامترهای اختیاری برای تست)."""
    user_id: int
    limit: int = Field(30, le=200)
    w_collab: float | None = None
    w_content: float | None = None
    w_popularity: float | None = None
    candidate_pool: int | None = None


class RecommendationDebug(BaseModel):
    """اطلاعات debug برای هر آهنگ پیشنهادی."""
    track: TrackOut
    score: float
    collab_score: float
    content_score: float
    pop_score: float


class UserProfileDebug(BaseModel):
    """نمای جامع از پروفایل یک کاربر برای admin panel."""
    user_id: int
    taste_vector: list[float] | None
    top_genres: list[dict]  # [{"id": 1, "name": "پاپ", "score": 3.5}, ...]
    top_artists: list[dict]
    recent_interactions: list[InteractionOut]
    total_interactions: int


class FeedbackSimulation(BaseModel):
    """شبیه‌سازی یک تعامل برای بررسی به‌روزرسانی real-time."""
    user_id: int
    track_id: int
    interaction_type: str  # play | like | skip | complete
    listen_duration: int = 0
