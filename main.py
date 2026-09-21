"""
Kafil Music API - Behavior-Based Personalization Backend
"""
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session, joinedload

from database import (
    SessionLocal, engine, Base, get_db,
    User, Song, Artist, Album, Genre, UserInteraction, InteractionType, Playlist,
)
import schemas
from auth import create_access_token, get_current_user, SECRET_KEY
import recommendations
import otp
from admin import setup_admin


# ایجاد جداول دیتابیس (برای پروداکشن از Alembic برای migration استفاده کنید)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Kafil Music API", version="3.0.0")

# لازم برای نگه‌داشتن سشن لاگین پنل ادمین
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# CORS برای دسترسی از اپ Flutter (وب/موبایل)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # در پروداکشن این را به دامنه/اپ مجاز محدود کنید
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# راه‌اندازی پنل مدیریت روی مسیر /admin
setup_admin(app)


# ==================== OTP Authentication ====================

@app.post("/auth/otp/request", status_code=status.HTTP_200_OK)
def request_otp(payload: schemas.OTPRequest, db: Session = Depends(get_db)):
    """
    درخواست کد OTP برای ورود یا ثبت‌نام
    کد به شماره موبایل کاربر ارسال می‌شود
    """
    otp.create_otp(db, payload.phone_number)
    return {"message": "کد تأیید به شماره موبایل شما ارسال شد", "phone_number": payload.phone_number}


@app.post("/auth/otp/verify", response_model=schemas.Token)
def verify_otp_and_login(payload: schemas.OTPVerify, db: Session = Depends(get_db)):
    """
    تأیید کد OTP و ورود کاربر
    اگر کاربر جدید باشد، حساب کاربری ایجاد می‌شود
    """
    if not otp.verify_otp(db, payload.phone_number, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="کد تأیید نامعتبر یا منقضی شده است"
        )

    user = otp.get_or_create_user_by_phone(db, payload.phone_number)

    # برای ایجاد توکن، از phone_number به عنوان شناسه استفاده می‌شود
    token = create_access_token(user.phone_number)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@app.post("/auth/set-credentials", response_model=schemas.UserOut)
def set_user_credentials(
    credentials: schemas.UserSetCredentials,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    مرحله دوم ثبت‌نام - تنظیم نام کاربری و رمز عبور
    فقط برای کاربرانی که با OTP وارد شده‌اند و هنوز username ندارند
    """
    # بررسی تکراری نبودن نام کاربری
    if db.query(User).filter(User.username == credentials.username, User.id != current_user.id).first():
        raise HTTPException(status_code=400, detail="این نام کاربری قبلاً گرفته شده است")

    # بررسی تکراری نبودن ایمیل (در صورت ارسال)
    if credentials.email:
        if db.query(User).filter(User.email == credentials.email, User.id != current_user.id).first():
            raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است")

    current_user.username = credentials.username
    current_user.email = credentials.email
    current_user.set_password(credentials.password)

    db.commit()
    db.refresh(current_user)

    return current_user


# ==================== Classic Auth (Backward Compatibility) ====================

@app.post("/users/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """ثبت‌نام کلاسیک با تمام اطلاعات - برای سازگاری با نسخه قبل"""
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


@app.post("/login", response_model=schemas.Token)
def login(user_in: schemas.UserLogin, db: Session = Depends(get_db)):
    """ورود کلاسیک با نام کاربری و رمز عبور"""
    user = db.query(User).filter(User.username == user_in.username).first()
    if not user or not user.check_password(user_in.password):
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")

    token = create_access_token(user.username if user.username else user.phone_number)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@app.get("/users/me", response_model=schemas.UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


# ==================== Songs & Metadata ====================

@app.get("/songs", response_model=List[schemas.SongOut])
def get_songs(
    genre: Optional[str] = None,
    artist_id: Optional[int] = None,
    q: Optional[str] = Query(None, description="جستجو در عنوان آهنگ"),
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Song).options(
        joinedload(Song.artist), joinedload(Song.album), joinedload(Song.genres)
    )
    if genre:
        query = query.join(Song.genres).filter(Genre.name == genre)
    if artist_id:
        query = query.filter(Song.artist_id == artist_id)
    if q:
        query = query.filter(Song.title.ilike(f"%{q}%"))

    return query.offset(skip).limit(limit).all()


@app.get("/songs/{song_id}", response_model=schemas.SongOut)
def get_song(song_id: int, db: Session = Depends(get_db)):
    song = (
        db.query(Song)
        .options(joinedload(Song.artist), joinedload(Song.album), joinedload(Song.genres))
        .filter(Song.id == song_id)
        .first()
    )
    if not song:
        raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")
    return song


@app.post("/songs", response_model=schemas.SongOut, status_code=status.HTTP_201_CREATED)
def create_song(song_in: schemas.SongCreate, db: Session = Depends(get_db)):
    """ثبت آهنگ جدید - برای پنل مدیریت محتوا"""
    artist = db.query(Artist).filter(Artist.id == song_in.artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="هنرمند پیدا نشد")

    if song_in.album_id and not db.query(Album).filter(Album.id == song_in.album_id).first():
        raise HTTPException(status_code=404, detail="آلبوم پیدا نشد")

    genres = []
    if song_in.genre_ids:
        genres = db.query(Genre).filter(Genre.id.in_(song_in.genre_ids)).all()

    song = Song(
        title=song_in.title,
        artist_id=song_in.artist_id,
        album_id=song_in.album_id,
        audio_url=song_in.audio_url,
        cover_url=song_in.cover_url,
        duration_sec=song_in.duration_sec,
        lyrics=song_in.lyrics,
        lyrics_timestamps=song_in.lyrics_timestamps,
        genres=genres,
    )
    db.add(song)
    db.commit()
    db.refresh(song)
    return song


@app.get("/artists", response_model=List[schemas.ArtistOut])
def get_artists(db: Session = Depends(get_db)):
    return db.query(Artist).all()


@app.get("/genres", response_model=List[schemas.GenreOut])
def get_genres(db: Session = Depends(get_db)):
    return db.query(Genre).all()


# ==================== Favorites ====================

@app.post("/songs/{song_id}/favorite")
def add_favorite(song_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")

    if song not in current_user.favorite_songs:
        current_user.favorite_songs.append(song)
        db.commit()

    return {"message": f"آهنگ «{song.title}» به علاقه‌مندی‌ها اضافه شد"}


@app.delete("/songs/{song_id}/favorite")
def remove_favorite(song_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")

    if song in current_user.favorite_songs:
        current_user.favorite_songs.remove(song)
        db.commit()

    return {"message": f"آهنگ «{song.title}» از علاقه‌مندی‌ها حذف شد"}


@app.get("/users/me/favorites", response_model=List[schemas.SongOut])
def get_favorites(current_user: User = Depends(get_current_user)):
    return current_user.favorite_songs


# ==================== Interaction Tracking ====================
# این بخش قلب سیستم شخصی‌سازی است - هر Play/Like/Skip/Search اینجا لاگ می‌شود

VALID_TYPES = {t.value for t in InteractionType}


@app.post("/interactions", response_model=schemas.InteractionOut, status_code=status.HTTP_201_CREATED)
def log_interaction(
    interaction_in: schemas.InteractionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ثبت هر تعامل کاربر (پخش، لایک، اسکیپ، جستجو، پخش کامل)"""
    if interaction_in.interaction_type not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"نوع تعامل نامعتبر است. مقادیر مجاز: {sorted(VALID_TYPES)}",
        )

    song = None
    if interaction_in.song_id is not None:
        song = db.query(Song).filter(Song.id == interaction_in.song_id).first()
        if not song:
            raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")

    itype = InteractionType(interaction_in.interaction_type)

    interaction = UserInteraction(
        user_id=current_user.id,
        song_id=interaction_in.song_id,
        interaction_type=itype,
        listen_duration=interaction_in.listen_duration,
        search_query=interaction_in.search_query,
    )
    db.add(interaction)

    # به‌روزرسانی شمارنده‌های آهنگ به صورت real-time
    if song:
        if itype == InteractionType.PLAY:
            song.view_count = (song.view_count or 0) + 1
        elif itype == InteractionType.LIKE:
            song.like_count = (song.like_count or 0) + 1
        elif itype == InteractionType.UNLIKE:
            song.like_count = max((song.like_count or 0) - 1, 0)
        elif itype == InteractionType.SKIP:
            song.skip_count = (song.skip_count or 0) + 1

    db.commit()
    db.refresh(interaction)
    return interaction


@app.get("/users/me/history", response_model=List[schemas.InteractionOut])
def get_my_history(
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(UserInteraction)
        .filter(UserInteraction.user_id == current_user.id)
        .order_by(UserInteraction.timestamp.desc())
        .limit(limit)
        .all()
    )


# ==================== Personalized (Dynamic) Playlists ====================

@app.get("/playlists/recommended", response_model=List[schemas.SongOut])
def get_recommended_playlist(
    limit: int = Query(30, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    پلی‌لیست پویا و شخصی‌سازی‌شده - بر اساس ژانر/هنرمندهای پرتکرار
    در تاریخچه تعاملات کاربر تولید می‌شود.
    """
    return recommendations.generate_personalized_playlist(db, current_user.id, limit=limit)


# ==================== User Playlists (Private) ====================

@app.post("/playlists", response_model=schemas.PlaylistOut, status_code=status.HTTP_201_CREATED)
def create_playlist(
    playlist_in: schemas.PlaylistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    playlist = Playlist(
        name=playlist_in.name,
        is_private=playlist_in.is_private,
        owner_id=current_user.id,
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return playlist


@app.get("/playlists/me", response_model=List[schemas.PlaylistOut])
def get_my_playlists(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Playlist).filter(Playlist.owner_id == current_user.id).all()


@app.post("/playlists/{playlist_id}/songs")
def add_song_to_playlist(
    playlist_id: int,
    payload: schemas.PlaylistAddSong,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    playlist = (
        db.query(Playlist)
        .filter(Playlist.id == playlist_id, Playlist.owner_id == current_user.id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="پلی‌لیست پیدا نشد یا متعلق به شما نیست")

    song = db.query(Song).filter(Song.id == payload.song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")

    if song not in playlist.songs:
        playlist.songs.append(song)
        db.commit()

    return {"message": f"آهنگ «{song.title}» به پلی‌لیست «{playlist.name}» اضافه شد"}


@app.delete("/playlists/{playlist_id}/songs/{song_id}")
def remove_song_from_playlist(
    playlist_id: int,
    song_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    playlist = (
        db.query(Playlist)
        .filter(Playlist.id == playlist_id, Playlist.owner_id == current_user.id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="پلی‌لیست پیدا نشد یا متعلق به شما نیست")

    song = db.query(Song).filter(Song.id == song_id).first()
    if song and song in playlist.songs:
        playlist.songs.remove(song)
        db.commit()

    return {"message": "آهنگ از پلی‌لیست حذف شد"}
