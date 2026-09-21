"""
احراز هویت JWT — توکن‌سازی و اعتبارسنجی.

بدون تغییر منطقی نسبت به نسخه قبل، فقط از app.config استفاده می‌کند.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db

if TYPE_CHECKING:
    from app.models import User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def create_access_token(subject: str) -> str:
    """
    ساخت توکن JWT.

    Args:
        subject: username یا phone_number کاربر.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.access_token_expire_hours)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    استخراج کاربر جاری از توکن JWT.

    در صورت توکن نامعتبر یا کاربر ناموجود، HTTPException 401 پرتاب می‌شود.
    """
    from app.models import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="اعتبارسنجی توکن ناموفق بود",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        identifier: str | None = payload.get("sub")
        if identifier is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter((User.username == identifier) | (User.phone_number == identifier))
        .first()
    )
    if user is None:
        raise credentials_exception
    return user


def get_current_admin(current_user: "User" = Depends(get_current_user)) -> "User":
    """
    وابستگیِ محافظت‌کننده: فقط کاربرِ ادمینِ فعال اجازه‌ی عبور دارد.

    برای endpointهای mutation (POST/PUT/DELETE) روی artists/songs/playlists
    استفاده می‌شود.
    """
    if not getattr(current_user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری غیرفعال است",
        )
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این عملیات فقط برای ادمین مجاز است",
        )
    return current_user
