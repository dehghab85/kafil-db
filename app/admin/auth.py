"""
Admin authentication backend — session-based login for SQLAdmin.
"""
from sqlalchemy.orm import Session as DbSession

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.config import get_settings
from app.db import SessionLocal
from app.models import User

settings = get_settings()


class AdminAuth(AuthenticationBackend):
    """
    احراز هویت پنل ادمین — فقط کاربران با is_admin=True و is_active=True.
    """

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        if not username or not password:
            return False

        db: DbSession = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            # Require both is_admin AND is_active; verify password hash
            if user and user.is_admin and user.is_active and user.check_password(password):
                request.session.update({
                    "admin_user": user.username,
                    "admin_user_id": str(user.id),
                })
                return True
            return False
        finally:
            db.close()

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "admin_user" in request.session
