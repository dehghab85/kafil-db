"""
Kafil Music - OTP Authentication System
سیستم احراز هویت با کد یکبار مصرف (One-Time Password)
"""
import random
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from database import OTPCode, User


OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
OTP_LENGTH = 6


def generate_otp_code() -> str:
    """تولید کد OTP شش رقمی تصادفی"""
    return "".join([str(random.randint(0, 9)) for _ in range(OTP_LENGTH)])


def send_otp_sms(phone_number: str, code: str) -> bool:
    """
    ارسال کد OTP به شماره موبایل از طریق سرویس پیامک

    TODO: اتصال به سرویس پیامک (کاوه‌نگار، فراز اس‌ام‌اس، و غیره)
    در حال حاضر فقط کد را در کنسول چاپ می‌کند (برای تست)
    """
    print(f"[OTP] ارسال کد {code} به شماره {phone_number}")
    # در پروداکشن:
    # response = sms_service.send(phone_number, f"کد تأیید کافیل: {code}")
    # return response.success
    return True


def create_otp(db: Session, phone_number: str) -> OTPCode:
    """
    ایجاد و ذخیره کد OTP جدید برای یک شماره موبایل
    کدهای قبلی همان شماره که منقضی نشده‌اند، باطل می‌شوند
    """
    # باطل کردن کدهای فعال قبلی
    db.query(OTPCode).filter(
        OTPCode.phone_number == phone_number,
        OTPCode.is_used == False,
        OTPCode.expires_at > datetime.utcnow()
    ).update({"is_used": True})

    code = generate_otp_code()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    otp = OTPCode(
        phone_number=phone_number,
        code=code,
        expires_at=expires_at,
        is_used=False
    )

    db.add(otp)
    db.commit()
    db.refresh(otp)

    # ارسال پیامک
    send_otp_sms(phone_number, code)

    return otp


def verify_otp(db: Session, phone_number: str, code: str) -> bool:
    """
    تأیید کد OTP وارد شده توسط کاربر
    در صورت موفقیت، کد به عنوان استفاده‌شده علامت‌گذاری می‌شود
    """
    otp = db.query(OTPCode).filter(
        OTPCode.phone_number == phone_number,
        OTPCode.code == code,
        OTPCode.is_used == False,
        OTPCode.expires_at > datetime.utcnow()
    ).first()

    if not otp:
        return False

    otp.is_used = True
    db.commit()
    return True


def get_or_create_user_by_phone(db: Session, phone_number: str) -> User:
    """
    پیدا کردن یا ایجاد کاربر بر اساس شماره موبایل
    برای احراز هویت OTP استفاده می‌شود
    """
    user = db.query(User).filter(User.phone_number == phone_number).first()

    if not user:
        user = User(
            phone_number=phone_number,
            is_phone_verified=True,
            username=None,  # در مرحله دوم تنظیم می‌شود
            password_hash=None,  # در مرحله دوم تنظیم می‌شود
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # اگر کاربر وجود داشت ولی شماره تأیید نشده بود
        if not user.is_phone_verified:
            user.is_phone_verified = True
            db.commit()

    return user
