"""
نمونه استفاده از API - Kafil Music
"""

# ==================== 1. احراز هویت با OTP ====================

# مرحله 1: درخواست کد OTP
POST /auth/otp/request
{
    "phone_number": "09123456789"
}

# Response:
{
    "message": "کد تأیید به شماره موبایل شما ارسال شد",
    "phone_number": "09123456789"
}

# مرحله 2: تأیید کد و ورود
POST /auth/otp/verify
{
    "phone_number": "09123456789",
    "code": "123456"
}

# Response:
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
        "id": 1,
        "username": null,
        "phone_number": "09123456789",
        "email": null,
        "is_phone_verified": true,
        "created_at": "2026-09-06T04:51:45.963Z",
        "preferred_genre_ids": null,
        "preferred_artist_ids": null
    }
}

# مرحله 3 (اختیاری): تنظیم نام کاربری و رمز عبور
POST /auth/set-credentials
Headers: Authorization: Bearer {access_token}
{
    "username": "ali_rezaei",
    "password": "securepass123",
    "email": "ali@example.com"
}

# ==================== 2. جستجو و دریافت آهنگ‌ها ====================

# دریافت لیست آهنگ‌ها
GET /songs?limit=20&skip=0

# جستجو در آهنگ‌ها
GET /songs?q=love&limit=10

# فیلتر بر اساس ژانر
GET /songs?genre=pop&limit=20

# فیلتر بر اساس خواننده
GET /songs?artist_id=5&limit=20

# دریافت جزئیات یک آهنگ (شامل شعر)
GET /songs/123
# Response:
{
    "id": 123,
    "title": "آهنگ عشق",
    "audio_url": "https://cdn.example.com/songs/123.mp3",
    "cover_url": "https://cdn.example.com/covers/123.jpg",
    "duration_sec": 245,
    "lyrics": "متن کامل شعر...",
    "lyrics_timestamps": "[{\"time\": 0, \"text\": \"خط اول\"}, {\"time\": 5.2, \"text\": \"خط دوم\"}]",
    "view_count": 1523,
    "like_count": 342,
    "artist": {
        "id": 5,
        "name": "محسن چاوشی",
        "avatar_url": "https://cdn.example.com/artists/5.jpg"
    },
    "album": {
        "id": 12,
        "title": "آلبوم جدید",
        "cover_url": "https://cdn.example.com/albums/12.jpg",
        "release_date": "2026-01-01T00:00:00"
    },
    "genres": [
        {"id": 1, "name": "پاپ"},
        {"id": 3, "name": "سنتی"}
    ]
}

# ==================== 3. ثبت تعاملات کاربر ====================

# ثبت پخش آهنگ
POST /interactions
Headers: Authorization: Bearer {access_token}
{
    "song_id": 123,
    "interaction_type": "play",
    "listen_duration": 0
}

# ثبت لایک
POST /interactions
Headers: Authorization: Bearer {access_token}
{
    "song_id": 123,
    "interaction_type": "like"
}

# ثبت پخش کامل
POST /interactions
Headers: Authorization: Bearer {access_token}
{
    "song_id": 123,
    "interaction_type": "complete",
    "listen_duration": 245
}

# ثبت اسکیپ
POST /interactions
Headers: Authorization: Bearer {access_token}
{
    "song_id": 123,
    "interaction_type": "skip",
    "listen_duration": 15
}

# ثبت جستجو
POST /interactions
Headers: Authorization: Bearer {access_token}
{
    "interaction_type": "search",
    "search_query": "love songs"
}

# ==================== 4. مدیریت علاقه‌مندی‌ها ====================

# افزودن به علاقه‌مندی‌ها
POST /songs/123/favorite
Headers: Authorization: Bearer {access_token}

# حذف از علاقه‌مندی‌ها
DELETE /songs/123/favorite
Headers: Authorization: Bearer {access_token}

# دریافت لیست علاقه‌مندی‌ها
GET /users/me/favorites
Headers: Authorization: Bearer {access_token}

# ==================== 5. پلی‌لیست شخصی‌سازی شده ====================

# دریافت پلی‌لیست پیشنهادی (بر اساس تعاملات کاربر)
GET /playlists/recommended?limit=30
Headers: Authorization: Bearer {access_token}

# این endpoint:
# - تعاملات کاربر را تحلیل می‌کند
# - علایق را به‌روزرسانی می‌کند
# - آهنگ‌های شخصی‌سازی شده برمی‌گرداند

# ==================== 6. مدیریت پلی‌لیست‌های شخصی ====================

# ایجاد پلی‌لیست جدید
POST /playlists
Headers: Authorization: Bearer {access_token}
{
    "name": "پلی‌لیست شب",
    "is_private": true
}

# دریافت پلی‌لیست‌های من
GET /playlists/me
Headers: Authorization: Bearer {access_token}

# افزودن آهنگ به پلی‌لیست
POST /playlists/5/songs
Headers: Authorization: Bearer {access_token}
{
    "song_id": 123
}

# حذف آهنگ از پلی‌لیست
DELETE /playlists/5/songs/123
Headers: Authorization: Bearer {access_token}

# ==================== 7. اطلاعات کاربر ====================

# دریافت اطلاعات پروفایل (شامل علایق ذخیره شده)
GET /users/me
Headers: Authorization: Bearer {access_token}

# Response:
{
    "id": 1,
    "username": "ali_rezaei",
    "phone_number": "09123456789",
    "email": "ali@example.com",
    "is_phone_verified": true,
    "created_at": "2026-09-06T04:51:45.963Z",
    "preferred_genre_ids": "[1, 3, 5]",  # JSON string - ژانرهای مورد علاقه
    "preferred_artist_ids": "[10, 23, 45]"  # JSON string - هنرمندان مورد علاقه
}

# دریافت تاریخچه تعاملات
GET /users/me/history?limit=50
Headers: Authorization: Bearer {access_token}

# ==================== 8. متادیتا ====================

# دریافت لیست هنرمندان
GET /artists

# دریافت لیست ژانرها
GET /genres

# ==================== نکات مهم ====================

# 1. همه درخواست‌های محافظت‌شده نیاز به Authorization header دارند:
#    Authorization: Bearer {access_token}

# 2. برای نمایش شعر به سبک Spotify:
#    - lyrics_timestamps را parse کنید (JSON array)
#    - هر آیتم دارای time (ثانیه) و text (متن) است
#    - با پیشرفت پخش، خط مربوطه را highlight کنید

# 3. علایق کاربر:
#    - به صورت خودکار از تعاملات محاسبه می‌شوند
#    - در preferred_genre_ids و preferred_artist_ids ذخیره می‌شوند
#    - برای نمایش پیشنهادات اختصاصی استفاده شوند

# 4. انواع تعامل (interaction_type):
#    - "play": شروع پخش آهنگ
#    - "complete": پخش کامل تا انتها
#    - "like": لایک
#    - "unlike": حذف لایک
#    - "skip": اسکیپ کردن
#    - "search": جستجو
