"""
scripts/create_admin.py
=======================
Creates or updates the admin user so SQLAdmin login works.

Run once after deployment or whenever the admin password needs resetting:
    python scripts/create_admin.py

Expected credentials after running:
    username : admin
    password : adminpassword123
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.db import SessionLocal
from app.models import User

settings = get_settings()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "adminpassword123"


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == ADMIN_USERNAME).first()

        if user is None:
            print(f"[CREATE] Admin user '{ADMIN_USERNAME}' does not exist — creating it.")
            user = User(
                username=ADMIN_USERNAME,
                # phone_number must be unique and NOT NULL if set; use a placeholder.
                phone_number="00000000000",
                email="admin@kafil.local",
                is_admin=True,
                is_active=True,
                is_phone_verified=False,
            )
            user.set_password(ADMIN_PASSWORD)
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[CREATE] Admin user created  — id={user.id}, username={user.username}")
            print(f"         is_admin={user.is_admin}, is_active={user.is_active}")
            print(f"         password_hash set via bcrypt.")
        else:
            print(f"[UPDATE] Admin user '{ADMIN_USERNAME}' already exists (id={user.id})")
            print(f"         Before — is_admin={user.is_admin}, is_active={user.is_active}")
            user.is_admin = True
            user.is_active = True
            user.set_password(ADMIN_PASSWORD)
            db.commit()
            db.refresh(user)
            print(f"[UPDATE] Updated   — is_admin={user.is_admin}, is_active={user.is_active}")
            print(f"         Password re-hashed with bcrypt.")
            # Quick verify
            if user.check_password(ADMIN_PASSWORD):
                print(f"[VERIFY] check_password() PASSED")
            else:
                print(f"[VERIFY] check_password() FAILED — check bcrypt installation")

        print("\nAdmin login credentials:")
        print(f"  username : {ADMIN_USERNAME}")
        print(f"  password : {ADMIN_PASSWORD}")
        print(f"  URL      : http://127.0.0.1:8000/admin/login")

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()