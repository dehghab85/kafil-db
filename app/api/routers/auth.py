"""
Authentication endpoints: OTP + classic username/password.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import (
    OTPRequest,
    OTPVerify,
    Token,
    UserCreate,
    UserLogin,
    UserOut,
    UserSetCredentials,
)
from app.security import create_access_token, create_otp, get_current_user, get_or_create_user_by_phone, verify_otp

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/otp/request", status_code=status.HTTP_200_OK)
def request_otp(payload: OTPRequest, db: Session = Depends(get_db)):
    """درخواست کد OTP برای ورود یا ثبت‌نام."""
    create_otp(db, payload.phone_number)
    return {"message": "کد تأیید به شماره موبایل شما ارسال شد", "phone_number": payload.phone_number}


@router.post("/otp/verify", response_model=Token)
def verify_otp_and_login(payload: OTPVerify, db: Session = Depends(get_db)):
    """تأیید کد OTP و ورود کاربر."""
    if not verify_otp(db, payload.phone_number, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="کد تأیید نامعتبر یا منقضی شده است",
        )

    user = get_or_create_user_by_phone(db, payload.phone_number)
    token = create_access_token(user.phone_number)

    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/set-credentials", response_model=UserOut)
def set_user_credentials(
    credentials: UserSetCredentials,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """مرحله دوم ثبت‌نام — تنظیم نام کاربری و رمز عبور."""
    if db.query(User).filter(User.username == credentials.username, User.id != current_user.id).first():
        raise HTTPException(status_code=400, detail="این نام کاربری قبلاً گرفته شده است")

    if credentials.email:
        if db.query(User).filter(User.email == credentials.email, User.id != current_user.id).first():
            raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است")

    current_user.username = credentials.username
    current_user.email = credentials.email
    current_user.set_password(credentials.password)
    db.commit()
    db.refresh(current_user)

    return current_user


# ---- Classic auth (backward compatibility) ----

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """ثبت‌نام کلاسیک (سازگاری با v3)."""
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است")
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="این نام کاربری قبلاً گرفته شده است")
    if db.query(User).filter(User.phone_number == user_in.phone_number).first():
        raise HTTPException(status_code=400, detail="این شماره موبایل قبلاً ثبت شده است")

    new_user = User(
        username=user_in.username,
        phone_number=user_in.phone_number,
        email=user_in.email,
        is_phone_verified=False,
    )
    new_user.set_password(user_in.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    """ورود کلاسیک با نام کاربری و رمز عبور."""
    user = db.query(User).filter(User.username == user_in.username).first()
    if not user or not user.check_password(user_in.password):
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")

    token = create_access_token(user.username if user.username else user.phone_number)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    """دریافت اطلاعات کاربر جاری."""
    return current_user
