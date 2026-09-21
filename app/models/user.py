"""
مدل User — کاربران و بردارهای علاقه‌مندی آن‌ها.

علاوه بر فیلدهای احراز هویت (username, password_hash, phone_number)، هر کاربر دارای:
  - taste_vector: بردار علاقه کاربر (محاسبه شده از تاریخچه‌ی تعاملات).
  - preferred_genre_ids / preferred_artist_ids: کش JSON از top ژانرها/هنرمندها (مانند نسخه قبل).
"""
from __future__ import annotations

from datetime import datetime, timezone

import bcrypt
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, relationship

from app.config import get_settings
from app.db import Base
from app.types import EmbeddingType

settings = get_settings()


# --- Many-to-Many association tables ---

user_favorites = Table(
    "user_favorites",
    Base.metadata,
    Column("user_id", Integer, primary_key=True),
    Column("track_id", Integer, primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=True, unique=True, index=True)
    # phone_number اکنون اختیاری است: کاربرِ username/password می‌تواند بدون
    # شماره موبایل ثبت‌نام کند. یکتایی همچنان برقرار است (چند NULL مجاز است).
    phone_number = Column(String(15), nullable=True, unique=True, index=True)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(128), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # --- بردار سلیقه کاربر (taste embedding) ---
    # بر اساس تاریخچه‌ی تعاملات محاسبه می‌شود (weighted sum از track embeddings).
    # در نسخه قبل این بردار به‌صورت on-the-fly محاسبه می‌شد؛ اکنون کش می‌شود.
    taste_vector = Column(EmbeddingType(dim=settings.content_dim), nullable=True)

    # کش JSON از علایق (سازگاری با v3.0)
    preferred_genre_ids = Column(Text, nullable=True)
    preferred_artist_ids = Column(Text, nullable=True)

    # --- Relations ---
    favorite_tracks: Mapped[list["Track"]] = relationship(
        "Track", secondary=user_favorites, back_populates="favorited_by"
    )
    interactions: Mapped[list["UserInteraction"]] = relationship(
        "UserInteraction", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """هش کردن رمز عبور با bcrypt."""
        pwd_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """بررسی صحت رمز عبور."""
        if not self.password_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))
        except (ValueError, AttributeError):
            return False