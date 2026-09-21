"""
Kafil Music - Pydantic Schemas
پاسخ‌های JSON تمیز و ساختاریافته برای فرانت‌اند Flutter
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# ==================== Auth ====================

class OTPRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)


class OTPVerify(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)
    code: str = Field(..., min_length=6, max_length=6)


class UserSetCredentials(BaseModel):
    """مرحله دوم ثبت‌نام - تنظیم نام کاربری و رمز عبور"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[EmailStr] = None


class UserCreate(BaseModel):
    """ثبت‌نام کلاسیک با تمام اطلاعات (برای سازگاری با نسخه قبل)"""
    username: str = Field(..., min_length=3, max_length=50)
    phone_number: str = Field(..., min_length=8, max_length=15)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    phone_number: str
    email: Optional[str] = None
    is_phone_verified: bool
    created_at: datetime
    preferred_genre_ids: Optional[str] = None  # JSON string
    preferred_artist_ids: Optional[str] = None  # JSON string

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ==================== Metadata (Artist / Album / Genre) ====================

class ArtistOut(BaseModel):
    id: int
    name: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class AlbumOut(BaseModel):
    id: int
    title: str
    cover_url: Optional[str] = None
    release_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class GenreOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# ==================== Songs ====================

class SongOut(BaseModel):
    id: int
    title: str
    audio_url: str
    cover_url: Optional[str] = None
    duration_sec: int
    lyrics: Optional[str] = None
    lyrics_timestamps: Optional[str] = None  # JSON string
    view_count: int
    like_count: int
    artist: ArtistOut
    album: Optional[AlbumOut] = None
    genres: List[GenreOut] = []

    class Config:
        from_attributes = True


class SongCreate(BaseModel):
    title: str
    artist_id: int
    album_id: Optional[int] = None
    audio_url: str
    cover_url: Optional[str] = None
    duration_sec: int = 0
    lyrics: Optional[str] = None
    lyrics_timestamps: Optional[str] = None
    genre_ids: List[int] = []


# ==================== Interaction Tracking ====================

class InteractionCreate(BaseModel):
    song_id: Optional[int] = None
    interaction_type: str  # play | complete | like | unlike | skip | search
    listen_duration: int = 0
    search_query: Optional[str] = None


class InteractionOut(BaseModel):
    id: int
    song_id: Optional[int]
    interaction_type: str
    listen_duration: int
    timestamp: datetime

    class Config:
        from_attributes = True


# ==================== Playlists ====================

class PlaylistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    is_private: bool = True


class PlaylistOut(BaseModel):
    id: int
    name: str
    is_private: bool
    is_auto_generated: bool
    created_at: datetime
    songs: List[SongOut] = []

    class Config:
        from_attributes = True


class PlaylistAddSong(BaseModel):
    song_id: int
