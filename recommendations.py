"""
Kafil Music - موتور شخصی‌سازی بر پایه رفتار کاربر (Behavior-Based Personalization Engine)

منطق کلی:
1. از روی جدول UserInteraction، امتیاز علاقه‌مندی کاربر به هر «ژانر» و «هنرمند» محاسبه می‌شود.
2. هر نوع تعامل وزن متفاوتی دارد (لایک > پخش کامل > پخش > جستجو، اسکیپ/آنلایک وزن منفی دارد).
3. تعاملات قدیمی‌تر با یک decay زمانی (نیم‌عمر ۳۰ روزه) وزن کمتری می‌گیرند.
4. آهنگ‌های کاندید بر اساس مجموع امتیاز ژانر+هنرمند رتبه‌بندی و به کاربر پیشنهاد می‌شوند.
5. اگر کاربر تاریخچه‌ای نداشته باشد (کاربر جدید)، آهنگ‌های ترند (Cold Start) برگردانده می‌شود.
6. علایق کاربر (preferred_genre_ids, preferred_artist_ids) در جدول User به‌صورت دوره‌ای به‌روزرسانی می‌شود.
"""
import json
from collections import defaultdict
from datetime import datetime
from typing import List, Set, Dict

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from database import Song, UserInteraction, InteractionType, Genre, User

# وزن هر نوع تعامل در محاسبه علاقه‌مندی
INTERACTION_WEIGHTS = {
    InteractionType.LIKE: 3.0,
    InteractionType.COMPLETE: 2.0,
    InteractionType.PLAY: 1.0,
    InteractionType.SEARCH: 0.5,
    InteractionType.SKIP: -1.5,
    InteractionType.UNLIKE: -2.0,
}

HALF_LIFE_DAYS = 30.0          # هر ۳۰ روز، اثر یک تعامل نصف می‌شود
RECENT_PLAY_EXCLUDE = 20       # از تکرار N آهنگ اخیر جلوگیری می‌شود
CANDIDATE_POOL_MULTIPLIER = 4  # اندازه استخر کاندیدها نسبت به limit نهایی


def _time_decay(timestamp: datetime) -> float:
    days_ago = max((datetime.utcnow() - timestamp).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (days_ago / HALF_LIFE_DAYS)


def _build_affinity_scores(db: Session, user_id: int):
    """محاسبه امتیاز علاقه‌مندی کاربر به هر ژانر/هنرمند از روی تاریخچه تعاملات"""
    interactions = (
        db.query(UserInteraction)
        .filter(UserInteraction.user_id == user_id, UserInteraction.song_id.isnot(None))
        .options(joinedload(UserInteraction.song).joinedload(Song.genres))
        .all()
    )

    genre_scores: dict = defaultdict(float)
    artist_scores: dict = defaultdict(float)
    disliked_song_ids: Set[int] = set()

    for inter in interactions:
        song = inter.song
        if song is None:
            continue

        weight = INTERACTION_WEIGHTS.get(inter.interaction_type, 0.0)
        decayed = weight * _time_decay(inter.timestamp)

        artist_scores[song.artist_id] += decayed
        for genre in song.genres:
            genre_scores[genre.id] += decayed

        if inter.interaction_type in (InteractionType.SKIP, InteractionType.UNLIKE):
            disliked_song_ids.add(song.id)

    return genre_scores, artist_scores, disliked_song_ids


def _recent_played_song_ids(db: Session, user_id: int, limit: int = RECENT_PLAY_EXCLUDE) -> Set[int]:
    """آهنگ‌های اخیرا پخش‌شده - برای جلوگیری از تکرار در پلی‌لیست جدید"""
    rows = (
        db.query(UserInteraction.song_id)
        .filter(
            UserInteraction.user_id == user_id,
            UserInteraction.interaction_type == InteractionType.PLAY,
        )
        .order_by(UserInteraction.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {r[0] for r in rows if r[0] is not None}


def _trending_songs(db: Session, limit: int, exclude_ids: Set[int]) -> List[Song]:
    """پرطرفدارترین آهنگ‌ها - برای کاربران جدید (Cold Start) یا پر کردن باقی‌مانده لیست"""
    query = db.query(Song).options(
        joinedload(Song.artist), joinedload(Song.album), joinedload(Song.genres)
    )
    if exclude_ids:
        query = query.filter(~Song.id.in_(exclude_ids))

    songs = query.all()
    songs.sort(key=lambda s: (s.view_count or 0) + (s.like_count or 0) * 3, reverse=True)
    return songs[:limit]


def update_user_preferences(db: Session, user_id: int) -> None:
    """
    به‌روزرسانی فیلدهای preferred_genre_ids و preferred_artist_ids کاربر
    بر اساس تحلیل تاریخچه تعاملات - این تابع می‌تواند به‌صورت دوره‌ای اجرا شود
    """
    genre_scores, artist_scores, _ = _build_affinity_scores(db, user_id)

    # ۵ ژانر و ۵ هنرمند برتر
    top_genre_ids = [gid for gid, _ in sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:5]]
    top_artist_ids = [aid for aid, _ in sorted(artist_scores.items(), key=lambda x: x[1], reverse=True)[:5]]

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.preferred_genre_ids = json.dumps(top_genre_ids) if top_genre_ids else None
        user.preferred_artist_ids = json.dumps(top_artist_ids) if top_artist_ids else None
        db.commit()


def generate_personalized_playlist(db: Session, user_id: int, limit: int = 30) -> List[Song]:
    """
    تولید پلی‌لیست شخصی‌سازی‌شده برای یک کاربر بر اساس تاریخچه رفتاری او
    (ژانرهای پرتکرار، هنرمندان پرشنیده‌شده).
    """
    genre_scores, artist_scores, disliked_ids = _build_affinity_scores(db, user_id)
    recent_ids = _recent_played_song_ids(db, user_id)
    exclude_ids = disliked_ids | recent_ids

    # به‌روزرسانی علایق کاربر در دیتابیس (برای استفاده در UI یا فیلترهای دیگر)
    update_user_preferences(db, user_id)

    # کاربر جدید بدون تاریخچه -> برگرداندن آهنگ‌های ترند
    if not genre_scores and not artist_scores:
        return _trending_songs(db, limit, exclude_ids)

    top_genre_ids = [gid for gid, _ in sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:5]]
    top_artist_ids = [aid for aid, _ in sorted(artist_scores.items(), key=lambda x: x[1], reverse=True)[:5]]

    query = db.query(Song).options(
        joinedload(Song.artist), joinedload(Song.album), joinedload(Song.genres)
    )
    if exclude_ids:
        query = query.filter(~Song.id.in_(exclude_ids))

    conditions = []
    if top_genre_ids:
        conditions.append(Song.genres.any(Genre.id.in_(top_genre_ids)))
    if top_artist_ids:
        conditions.append(Song.artist_id.in_(top_artist_ids))
    if conditions:
        query = query.filter(or_(*conditions))

    candidates = query.limit(limit * CANDIDATE_POOL_MULTIPLIER).all()

    def score_song(song: Song) -> float:
        score = artist_scores.get(song.artist_id, 0.0)
        score += sum(genre_scores.get(g.id, 0.0) for g in song.genres)
        # محبوبیت عمومی به عنوان معیار تعیین‌کننده در تساوی امتیاز
        score += (song.view_count or 0) * 0.001 + (song.like_count or 0) * 0.01
        return score

    ranked = sorted(candidates, key=score_song, reverse=True)[:limit]

    # اگر کاندیدهای کافی پیدا نشد، با آهنگ‌های ترند پر می‌شود
    if len(ranked) < limit:
        filler_exclude = exclude_ids | {s.id for s in ranked}
        ranked.extend(_trending_songs(db, limit - len(ranked), filler_exclude))

    return ranked
