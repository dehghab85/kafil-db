"""
Kafil Music - Database Models
سیستم شخصی‌سازی بر پایه رفتار کاربر (Behavior-Based Personalization)
"""
import os
import enum
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Table,
    Boolean, Enum, Text, Index, create_engine,
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from dotenv import load_dotenv
import bcrypt

# خواندن متغیرهای محیطی از فایل .env در همان پوشه این فایل
load_dotenv(Path(__file__).resolve().parent / ".env")

# ---------------------------------------------------------------------------
# اتصال به دیتابیس
# در پروداکشن مقدار DATABASE_URL را از متغیر محیطی بخوان (مثلا Postgres)
# برای هم‌زمانی بالا (high-concurrency)، sqlite مناسب پروداکشن نیست.
# ---------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kafil_music.db")

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency تک‌منظوره برای FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# جداول واسط (Many-to-Many)
# ---------------------------------------------------------------------------

user_favorites = Table(
    "user_favorites", Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("song_id", Integer, ForeignKey("songs.id", ondelete="CASCADE"), primary_key=True),
)

song_genres = Table(
    "song_genres", Base.metadata,
    Column("song_id", Integer, ForeignKey("songs.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

playlist_songs = Table(
    "playlist_songs", Base.metadata,
    Column("playlist_id", Integer, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("song_id", Integer, ForeignKey("songs.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, default=0),
)


class InteractionType(str, enum.Enum):
    """انواع تعامل کاربر - پایه موتور شخصی‌سازی"""
    PLAY = "play"
    COMPLETE = "complete"   # آهنگ تا انتها پخش شد
    LIKE = "like"
    UNLIKE = "unlike"
    SKIP = "skip"
    SEARCH = "search"


# ---------------------------------------------------------------------------
# مدل‌ها
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=True, unique=True, index=True)  # Nullable until set in step 2
    phone_number = Column(String(15), nullable=False, unique=True)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(128), nullable=True)  # Nullable for OTP-only users initially
    is_admin = Column(Boolean, default=False, nullable=False)
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # User preference tracking for personalization (stored as JSON text)
    preferred_genre_ids = Column(Text, nullable=True)  # JSON array: [1, 3, 5]
    preferred_artist_ids = Column(Text, nullable=True)  # JSON array: [10, 23, 45]

    favorite_songs = relationship("Song", secondary=user_favorites, back_populates="favorited_by")
    interactions = relationship("UserInteraction", back_populates="user", cascade="all, delete-orphan")
    playlists = relationship("Playlist", back_populates="owner", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        """هش کردن پسورد با bcrypt"""
        pwd_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """بررسی صحت پسورد"""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))
        except (ValueError, AttributeError):
            return False


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True, index=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)

    albums = relationship("Album", back_populates="artist")
    songs = relationship("Song", back_populates="artist")


class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    release_date = Column(DateTime, nullable=True)
    cover_url = Column(String(500), nullable=True)

    artist = relationship("Artist", back_populates="albums")
    songs = relationship("Song", back_populates="album")


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)

    songs = relationship("Song", secondary=song_genres, back_populates="genres")


class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True)
    audio_url = Column(String(500), nullable=False)
    cover_url = Column(String(500), nullable=True)
    duration_sec = Column(Integer, default=0)
    release_date = Column(DateTime, nullable=True)

    # lyrics fields for Spotify-style synchronized lyrics display
    lyrics = Column(Text, nullable=True)  # Full lyrics text
    lyrics_timestamps = Column(Text, nullable=True)  # JSON array of {time: seconds, text: "lyric line"}

    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    skip_count = Column(Integer, default=0)

    artist = relationship("Artist", back_populates="songs")
    album = relationship("Album", back_populates="songs")
    genres = relationship("Genre", secondary=song_genres, back_populates="songs")
    favorited_by = relationship("User", secondary=user_favorites, back_populates="favorite_songs")
    interactions = relationship("UserInteraction", back_populates="song", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_song_artist_title", "artist_id", "title"),
    )


class UserInteraction(Base):
    """هسته اصلی موتور شخصی‌سازی - هر اکشن کاربر اینجا لاگ می‌شود"""
    __tablename__ = "user_interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    song_id = Column(Integer, ForeignKey("songs.id", ondelete="CASCADE"), nullable=True, index=True)
    interaction_type = Column(Enum(InteractionType), nullable=False, index=True)
    listen_duration = Column(Integer, default=0)   # ثانیه - برای Play/Complete
    search_query = Column(String(200), nullable=True)  # برای Search
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="interactions")
    song = relationship("Song", back_populates="interactions")

    __table_args__ = (
        Index("ix_interaction_user_time", "user_id", "timestamp"),
    )


class Playlist(Base):
    """پلی‌لیست‌های خصوصی کاربر + پلی‌لیست‌های خودکار تولیدشده"""
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_private = Column(Boolean, default=True)
    is_auto_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="playlists")
    songs = relationship("Song", secondary=playlist_songs, order_by=playlist_songs.c.position)


class OTPCode(Base):
    """کدهای یکبار مصرف برای احراز هویت با شماره موبایل"""
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(15), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_otp_phone_expiry", "phone_number", "expires_at"),
    )
