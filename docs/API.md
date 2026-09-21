# API Reference

All endpoints require `Authorization: Bearer TOKEN` unless marked as public.

---

## Authentication

### `POST /auth/otp/request`

درخواست کد OTP برای ورود.

**Request:**
```json
{
  "phone_number": "09123456789"
}
```

**Response (200):**
```json
{
  "message": "کد تأیید به شماره موبایل شما ارسال شد",
  "phone_number": "09123456789"
}
```

---

### `POST /auth/otp/verify`

تأیید کد و دریافت JWT.

**Request:**
```json
{
  "phone_number": "09123456789",
  "code": "123456"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": { ... }
}
```

---

### `POST /auth/set-credentials`

تنظیم نام کاربری و رمز عبور (مرحله 2 ثبت‌نام).

**Auth:** Required

**Request:**
```json
{
  "username": "ali_rezaei",
  "password": "securepass123",
  "email": "ali@example.com"
}
```

**Response (200):**
```json
{
  "id": 1,
  "username": "ali_rezaei",
  "phone_number": "09123456789",
  "email": "ali@example.com",
  ...
}
```

---

## Tracks

### `GET /songs`
### `GET /tracks`

دریافت لیست آهنگ‌ها (جستجو و فیلتر).

**Query Parameters:**
- `q` (str): جستجو در عنوان
- `genre` (str): فیلتر بر اساس ژانر
- `artist_id` (int): فیلتر بر اساس هنرمند
- `skip` (int): pagination offset
- `limit` (int): page size (max 200)

**Response (200):**
```json
[
  {
    "id": 1,
    "title": "آهنگ عشق",
    "audio_url": "https://...",
    "duration_sec": 245,
    "view_count": 1523,
    "like_count": 342,
    "artist": { "id": 5, "name": "محسن چاوشی" },
    ...
  }
]
```

---

### `GET /songs/{track_id}`
### `GET /tracks/{track_id}`

دریافت جزئیات یک آهنگ.

**Response (200):**
```json
{
  "id": 1,
  "title": "آهنگ عشق",
  ...
}
```

---

### `POST /songs/favorite`
### `POST /tracks/{track_id}/favorite`

افزودن آهنگ به علاقه‌مندی‌ها.

**Auth:** Required

**Response (200):**
```json
{
  "message": "آهنگ «...» به علاقه‌مندی‌ها اضافه شد"
}
```

---

### `GET /users/me/favorites`

دریافت علاقه‌مندی‌های کاربر.

**Auth:** Required

**Response (200):**
```json
[ ... list of TrackOut ... ]
```

---

## Interactions

### `POST /interactions`

ثبت یک تعامل (play, like, skip, complete, search).

**Auth:** Required

**Request:**
```json
{
  "track_id": 123,
  "interaction_type": "play",
  "listen_duration": 0
}
```

**Interaction Types:**
- `play` — شروع پخش
- `complete` — پخش کامل (listen_duration ≈ track.duration_sec)
- `like` — لایک
- `unlike` — حذف لایک
- `skip` — اسکیپ
- `search` — جستجو (search_query بجای track_id)

**Response (201):**
```json
{
  "id": 1,
  "user_id": 1,
  "track_id": 123,
  "interaction_type": "play",
  "timestamp": "2026-09-15T09:28:38Z",
  ...
}
```

---

### `GET /users/me/history`

دریافت تاریخچه تعاملات.

**Auth:** Required

**Query:**
- `limit` (int): max 200

**Response (200):**
```json
[ ... list of InteractionOut ... ]
```

---

## Playlists

### `GET /playlists/recommended`

**پلی‌لیست شخصی‌سازی‌شده (v4 ML engine).**

**Auth:** Required

**Query:**
- `limit` (int): top-K (max 100, default 30)

**Response (200):**
```json
[ ... list of TrackOut ranked by recommendation score ... ]
```

---

### `POST /playlists`

ایجاد پلی‌لیست جدید.

**Auth:** Required

**Request:**
```json
{
  "name": "پلی‌لیست شب",
  "is_private": true
}
```

**Response (201):**
```json
{
  "id": 1,
  "name": "پلی‌لیست شب",
  "is_private": true,
  "songs": [],
  ...
}
```

---

### `POST /playlists/{playlist_id}/songs`

افزودن آهنگ به پلی‌لیست.

**Auth:** Required

**Request:**
```json
{
  "song_id": 123
}
```

---

## Admin Only

### `POST /recommendations/pipeline/run`

اجرای کامل ML pipeline (admin only).

**Auth:** Required (admin user)

**Response (200):**
```json
{
  "status": "completed",
  "users_with_vectors": 1234,
  "items_with_vectors": 5678,
  "total_tracks": 6000
}
```

---

### `POST /recommendations/debug`

دریافت recommendation با score breakdown (admin only).

**Auth:** Required (admin)

**Request:**
```json
{
  "user_id": 1,
  "limit": 10,
  "w_collab": 0.5,
  "w_content": 0.35,
  "w_popularity": 0.15
}
```

**Response (200):**
```json
[
  {
    "track": { ... TrackOut ... },
    "score": 0.78,
    "collab_score": 0.65,
    "content_score": 0.72,
    "pop_score": 0.45
  },
  ...
]
```

---

### `GET /recommendations/users/{user_id}/profile`

دریافت پروفایل کاربر (admin only).

**Auth:** Required (admin)

**Response (200):**
```json
{
  "user_id": 1,
  "taste_vector": [0.1, 0.2, ...],
  "top_genres": [{"id": 1, "name": "پاپ"}],
  "top_artists": [{"id": 5, "name": "محسن چاوشی"}],
  "recent_interactions": [ ... ],
  "total_interactions": 567
}
```

---

### `POST /recommendations/simulate-feedback`

شبیه‌سازی یک تعامل برای testing (admin only).

**Auth:** Required (admin)

**Request:**
```json
{
  "user_id": 1,
  "track_id": 123,
  "interaction_type": "like",
  "listen_duration": 0
}
```

**Response (200):**
```json
{
  "status": "updated",
  "user_id": 1,
  "track_id": 123,
  "new_taste_vector": [0.1, 0.2, ...]
}
```

---

## Error Responses

All errors return JSON:

```json
{
  "detail": "نام کاربری یا رمز عبور اشتباه است"
}
```

**Common Status Codes:**
- `200` — OK
- `201` — Created
- `400` — Bad Request
- `401` — Unauthorized (invalid token)
- `403` — Forbidden (admin required)
- `404` — Not Found
- `500` — Internal Server Error
