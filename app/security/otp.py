"""
سیستم OTP — ساخت، ارسال و تأیید کدهای یکبار مصرف.

بدون تغییر منطقی نسبت به نسخه قبل.
TODO: اتصال واقعی به سرویس پیامک (کاوه‌نگار، فراز، ...).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import OTPCode, User

settings = get_settings()


def generate_otp_code() -> str:
    """تولید کد OTP تصادفی."""
    return "".join(str(random.randint(0, 9)) for _ in range(settings.otp_length))


def send_otp_sms(phone_number: str, code: str) -> bool:
    """
    ارسال کد OTP به شماره موبایل.

    TODO: اتصال به سرویس پیامک.
    در حال حاضر فقط در کنسول چاپ می‌شود (برای تست).
    """
    print(f"[OTP] ارسال کد {code} به شماره {phone_number}")
    # در پروداکشن:
    # response = sms_service.send(phone_number, f"کد تأیید کافیل: {code}")
    # return response.success
    return True


def create_otp(db: Session, phone_number: str) -> OTPCode:
    """
    ایجاد و ذخیره کد OTP جدید؛ کدهای قبلی باطل می‌شوند.
    """
    # Invalidate existing active codes
    db.query(OTPCode).filter(
        OTPCode.phone_number == phone_number,
        OTPCode.is_used == False,  # noqa: E712
        OTPCode.expires_at > datetime.now(timezone.utc),
    ).update({"is_used": True})

    code = generate_otp_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expiry_minutes)

    otp = OTPCode(
        phone_number=phone_number,
        code=code,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)

    send_otp_sms(phone_number, code)
    return otp


def verify_otp(db: Session, phone_number: str, code: str) -> bool:
    """
    تأیید کد OTP.

    در صورت موفقیت، کد به‌عنوان استفاده‌شده علامت‌گذاری می‌شود.
    """
    otp = (
        db.query(OTPCode)
        .filter(
            OTPCode.phone_number == phone_number,
            OTPCode.code == code,
            OTPCode.is_used == False,  # noqa: E712
            OTPCode.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if not otp:
        return False

    otp.is_used = True
    db.commit()
    return True


def get_or_create_user_by_phone(db: Session, phone_number: str) -> User:
    """
    پیدا کردن یا ایجاد کاربر بر اساس شماره موبایل.
    """
    user = db.query(User).filter(User.phone_number == phone_number).first()

    if not user:
        user = User(
            phone_number=phone_number,
            is_phone_verified=True,
            username=None,
            password_hash=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if not user.is_phone_verified:
            user.is_phone_verified = True
            db.commit()

    return user
