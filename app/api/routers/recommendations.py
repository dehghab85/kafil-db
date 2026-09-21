"""
Recommendation admin endpoints — pipeline control, user profiling, simulator.

این endpoint ها برای admin panel و debugging هستند.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import FeedbackSimulation, RecommendationRequest
from app.security import get_current_user
from app.services.recommendation import (
    get_recommendations_with_debug,
    get_user_profile_debug,
    handle_feedback,
    run_full_pipeline,
)

router = APIRouter(prefix="/recommendations", tags=["Recommendations (Admin)"])


@router.post("/pipeline/run")
def trigger_pipeline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    اجرای کامل pipeline (admin only).

    این عملیات سنگین است و باید به‌صورت دوره‌ای یا دستی اجرا شود.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="فقط ادمین مجاز به اجرای pipeline است")

    result = run_full_pipeline(db)
    return result


@router.post("/debug")
def get_recommendations_debug(
    req: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    دریافت recommendation همراه با scores تفکیک‌شده (برای debugging).

    در admin panel می‌توان وزن‌های w_collab, w_content, w_popularity را تنظیم کرد.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="فقط ادمین")

    results = get_recommendations_with_debug(
        db,
        req.user_id,
        req.limit,
        req.w_collab,
        req.w_content,
        req.w_popularity,
    )
    return results


@router.get("/users/{user_id}/profile")
def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    دریافت اطلاعات کامل پروفایل یک کاربر (taste vector, top genres/artists, interactions).
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="فقط ادمین")

    return get_user_profile_debug(db, user_id)


@router.post("/simulate-feedback")
def simulate_feedback(
    sim: FeedbackSimulation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    شبیه‌سازی یک تعامل برای بررسی real-time update.

    برای testing در admin panel استفاده می‌شود.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="فقط ادمین")

    result = handle_feedback(
        db, sim.user_id, sim.track_id, sim.interaction_type, sim.listen_duration
    )
    return result
