import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app

# ۱. تنظیم دیتابیس مخصوص تست (در حافظه RAM ساخته می‌شود تا دیتابیس اصلی خراب نشود)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ۲. جایگزین کردن دیتابیس اصلی با دیتابیس تست در FastAPI
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    """ایجاد جداول در ابتدای هر تست و پاکسازی در پایان تست"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

# --- شروع تست‌ها ---

def test_register_user():
    """تست موفقیت‌آمیز بودن ثبت‌نام"""
    response = client.post(
        "/users/register", # مطمئن شو مسیر در main.py دقیقا همین باشد
        json={
            "username": "testuser",
            "phone_number": "09123456789",
            "email": "test@example.com",
            "password": "securepassword"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data

def test_login_success():
    """تست لاگین با اطلاعات درست"""
    # ابتدا کاربر را ثبت نام می‌کنیم
    client.post(
        "/users/register",
        json={"username": "loginuser", "phone_number": "123", "email": "l@t.com", "password": "123"}
    )
    
    # حالا تست لاگین
    response = client.post(
        "/login",
        json={"username": "loginuser", "password": "123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_fail():
    """تست لاگین با رمز عبور اشتباه"""
    client.post(
        "/users/register",
        json={"username": "failuser", "phone_number": "999", "email": "fail@t.com", "password": "123"}
    )
    
    response = client.post(
        "/login",
        json={"username": "failuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "نام کاربری یا رمز عبور اشتباه است"

def test_get_songs_empty():
    """تست دریافت لیست آهنگ‌ها (وقتی دیتابیس خالی است)"""
    response = client.get("/songs")
    assert response.status_code == 200
    assert response.json() == []
