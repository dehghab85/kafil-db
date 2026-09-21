"""
Kafil Music - Authentication
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from database import get_db, User

# خواندن متغیرهای محیطی از فایل .env (اگر وجود داشته باشد)
load_dotenv()

# کلید امضای JWT حتما باید از متغیر محیطی خوانده شود، نه هاردکد در کد!
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "متغیر محیطی JWT_SECRET_KEY تنظیم نشده است. "
        "یک مقدار تصادفی و امن در فایل .env قرار دهید "
        "(مثلا با دستور: python -c \"import secrets; print(secrets.token_hex(32))\")"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_access_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """استخراج و اعتبارسنجی کاربر جاری از روی توکن JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="اعتبارسنجی توکن ناموفق بود",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        identifier: Optional[str] = payload.get("sub")
        if identifier is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # جستجو بر اساس username یا phone_number
    user = db.query(User).filter(
        (User.username == identifier) | (User.phone_number == identifier)
    ).first()

    if user is None:
        raise credentials_exception
    return user