"""
اشکال‌زدایی موقت: بررسی نوع مقدار فیلدهای فایل در on_model_change.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ["MEDIA_STORAGE_BACKEND"] = "local"
os.environ.setdefault("JWT_SECRET_KEY", "validation-secret")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import db as db_module  # noqa: E402

TEST_DB = ROOT / "debug_admin.db"
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

from app.admin.views import ArtistAdmin  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Artist, User  # noqa: E402

_original = ArtistAdmin.on_model_change


async def _debug(self, data, model, is_created, request):
    print("  [debug] on_model_change data:")
    for k, v in data.items():
        print(f"    {k!r} = {type(v).__module__}.{type(v).__name__} -> {str(v)[:70]!r}")
    form = await request.form()
    print("  [debug] request.form() multi_items:")
    for k, v in form.multi_items():
        print(f"    {k!r} = {type(v).__module__}.{type(v).__name__} -> {str(v)[:70]!r}")
    return await _original(self, data, model, is_created, request)


ArtistAdmin.on_model_change = _debug


def main() -> None:
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
    resp = client.post(
        "/admin/login",
        data={"username": "admin", "password": "adminpassword123"},
        follow_redirects=False,
    )
    print(f"login -> {resp.status_code}")

    resp = client.post(
        "/admin/artist/create",
        data={"name": "artist-x", "bio": "b", "save": "Save"},
        files={"cover_url": ("cover.png", PNG_BYTES, "image/png")},
        follow_redirects=False,
    )
    print(f"create -> {resp.status_code}")
    if resp.status_code == 400:
        print(resp.text[:3000])

    session = db_module.SessionLocal()
    for a in session.query(Artist).all():
        print(f"artist id={a.id} name={a.name!r} cover_url={a.cover_url!r}")
    session.close()
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


if __name__ == "__main__":
    main()