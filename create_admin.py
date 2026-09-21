"""
اسکریپت ساخت کاربر ادمین
اجرا: python create_admin.py
"""
import getpass

from database import SessionLocal, Base, engine, User

Base.metadata.create_all(bind=engine)


def main():
    print("=== ساخت کاربر ادمین ===")
    username = input("نام کاربری: ").strip()
    email = input("ایمیل: ").strip()
    phone = input("شماره موبایل: ").strip()
    password = getpass.getpass("پسورد: ")
    password_confirm = getpass.getpass("تکرار پسورد: ")

    if password != password_confirm:
        print("❌ پسوردها یکسان نیستند.")
        return

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            existing.is_admin = True
            existing.set_password(password)
            db.commit()
            print(f"✅ کاربر «{username}» از قبل وجود داشت و به ادمین ارتقا یافت.")
            return

        admin_user = User(username=username, email=email, phone_number=phone, is_admin=True)
        admin_user.set_password(password)
        db.add(admin_user)
        db.commit()
        print(f"✅ کاربر ادمین «{username}» با موفقیت ساخته شد.")
        print("حالا می‌توانید با همین یوزرنیم/پسورد وارد /admin شوید.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
