"""
اعتبارسنجی سرتاسریِ پنل ادمین (موقت — بخشی از تست‌های پروژه نیست):
  1) mount شدن /static در FastAPI
  2) آپلود واقعی کاور مداح از فرم SQLAdmin (multipart) با بک‌اند محلی
     → فایل روی دیسک با نام UUID + مقداردهی Artist.cover_url
  3) نمایش خوانای نام مداح در لیست نوحه‌ها (SongAdmin)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# بک‌اند محلی تا آپلود روی static/uploads برود (مستقل از .env کاربر).
os.environ["MEDIA_STORAGE_BACKEND"] = "local"
os.environ.setdefault("JWT_SECRET_KEY", "validation-secret")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import db as db_module  # noqa: E402

# دیتابیس موقت SQLite روی فایل تا هم admin و هم app از یک DB استفاده کنند.
TEST_DB = ROOT / "validation_admin.db"
if TEST_DB.exists():
    TEST_DB.unlink()
engine = create_engine(f"sqlite:///{TEST_DB}", connect_args={"check_same_thread": False})
db_module.engine = engine
db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05570c1f8b0000000049454e44ae426082"
)


def main() -> None:
    from app.db import Base
    from app.main import app
    from app.models import Artist, Song, User

    Base.metadata.create_all(bind=engine)

    session = db_module.SessionLocal()
    admin_user = User(
        username="admin",
        phone_number="00000000000",
        email="admin@kafil.local",
        is_admin=True,
        is_active=True,
    )
    admin_user.set_password("adminpassword123")
    session.add(admin_user)
    session.commit()
    session.close()

    client = TestClient(app)

    # ---- 1) /static mount ----
    static_dir = ROOT / "static"
    probe = static_dir / "probe.txt"
    static_dir.mkdir(parents=True, exist_ok=True)
    probe.write_text("static-ok", encoding="utf-8")
    resp = client.get("/static/probe.txt")
    assert resp.status_code == 200 and resp.text == "static-ok", resp.status_code
    print(f"[1] GET /static/probe.txt -> {resp.status_code} (StaticFiles mounted)")
    probe.unlink()

    # ---- login ----
    resp = client.post(
        "/admin/login",
        data={"username": "admin", "password": "adminpassword123"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), (resp.status_code, resp.text[:400])
    print(f"[2] admin login -> {resp.status_code}")

    # ---- 2) create Artist with cover upload ----
    resp = client.post(
        "/admin/artist/create",
        data={
            "name": "سید مجید بنی‌فاطمه",
            "bio": "مداح اهل بیت",
            "cover_url": ("cover.png", PNG_BYTES, "image/png"),
            "save": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), (resp.status_code, resp.text[:2000])
    print(f"[3] POST /admin/artist/create -> {resp.status_code}")

    session = db_module.SessionLocal()
    artist = session.query(Artist).filter(Artist.name == "سید مجید بنی‌فاطمه").one()
    cover = artist.cover_url
    print(f"[4] Artist.cover_url = {cover}")
    assert cover and cover.startswith("/static/uploads/artists/"), cover
    saved = static_dir / cover[len("/static/"):]
    assert saved.is_file(), f"uploaded file not on disk: {saved}"
    assert saved.stat().st_size == len(PNG_BYTES)
    assert len(saved.stem) == 32, f"filename should be a UUID hex, got {saved.name}"
    print(f"[5] file on disk: {saved.relative_to(ROOT)} ({saved.stat().st_size} bytes, uuid name)")

    resp = client.get(cover)
    assert resp.status_code == 200 and resp.content == PNG_BYTES
    print(f"[6] GET {cover} -> 200 (image served byte-identical)")

    # ---- edit without a new file → cover preserved ----
    resp = client.post(
        f"/admin/artist/edit/{artist.id}",
        data={"name": artist.name, "bio": "به‌روزشده", "cover_url": (None, b""), "save": "Save"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.status_code
    session.expire_all()
    artist = session.query(Artist).get(artist.id)
    assert artist.cover_url == cover, f"cover changed unexpectedly: {artist.cover_url}"
    assert artist.bio == "به‌روزشده"
    print("[7] edit with empty file field kept the existing cover")

    # ---- 3) Song list shows readable artist name ----
    song = Song(title="امشب شب قدره", artist_id=artist.id, audio_url="/static/uploads/x.mp3")
    session.add(song)
    session.commit()
    artist_id = artist.id
    session.close()

    resp = client.get("/admin/song/list")
    assert resp.status_code == 200, resp.status_code
    body = resp.text
    assert "سید مجید بنی‌فاطمه" in body, "artist name missing from Song list"
    assert "&lt;Artist" not in body, "raw repr displayed in Song list"
    assert "امشب شب قدره" in body
    print("[8] GET /admin/song/list -> readable artist name rendered")

    resp = client.get("/admin/artist/list")
    assert resp.status_code == 200 and '<img src="/static/uploads/artists/' in resp.text
    print("[9] GET /admin/artist/list -> thumbnail <img> rendered")

    # پاک‌کردن فایل آپلودشده در پایان آزمون
    saved.unlink(missing_ok=True)
    session = db_module.SessionLocal()
    session.query(Song).delete()
    session.query(Artist).delete()
    session.query(User).delete()
    session.commit()
    session.close()
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)

    print("\nALL ADMIN INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    main()