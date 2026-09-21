"""
Custom admin views — Dashboard, ML Pipeline Control, Statistics.
"""
from sqladmin import BaseView, expose
from sqlalchemy import func, select
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.db import SessionLocal
from app.models import Artist, Genre, Track, User, UserInteraction


class DashboardView(BaseView):
    """
    Custom admin dashboard — statistics, charts, recent activity.
    """
    
    name = "داشبورد"
    icon = "fa-solid fa-chart-pie"
    
    @expose("/dashboard", methods=["GET"])
    async def dashboard(self, request: Request):
        """Main dashboard page with statistics and charts."""
        db = SessionLocal()
        try:
            # Gather statistics
            stats = {
                "total_users": db.query(func.count(User.id)).scalar() or 0,
                "total_tracks": db.query(func.count(Track.id)).scalar() or 0,
                "total_artists": db.query(func.count(Artist.id)).scalar() or 0,
                "total_genres": db.query(func.count(Genre.id)).scalar() or 0,
                "total_interactions": db.query(func.count(UserInteraction.id)).scalar() or 0,
            }
            
            # Recent interactions (last 10)
            recent_interactions = (
                db.query(UserInteraction)
                .order_by(UserInteraction.timestamp.desc())
                .limit(10)
                .all()
            )
            
            # Top 5 tracks by plays
            top_tracks = (
                db.query(Track)
                .order_by(Track.view_count.desc())
                .limit(5)
                .all()
            )
            
            # Top 5 genres by track count
            top_genres_data = (
                db.query(
                    Genre.name,
                    func.count(Track.id).label("track_count")
                )
                .join(Track.genres)
                .group_by(Genre.id, Genre.name)
                .order_by(func.count(Track.id).desc())
                .limit(5)
                .all()
            )
            
            # Interaction type distribution
            interaction_types = (
                db.query(
                    UserInteraction.interaction_type,
                    func.count(UserInteraction.id).label("count")
                )
                .group_by(UserInteraction.interaction_type)
                .all()
            )
            
            return await self.templates.TemplateResponse(
                "dashboard.html",
                {
                    "request": request,
                    "stats": stats,
                    "recent_interactions": recent_interactions,
                    "top_tracks": top_tracks,
                    "top_genres": top_genres_data,
                    "interaction_types": interaction_types,
                },
            )
        finally:
            db.close()


class MLPipelineView(BaseView):
    """
    ML Pipeline control panel — trigger jobs, view status.
    """
    
    name = "پایپلاین ML"
    icon = "fa-solid fa-robot"
    
    @expose("/ml-pipeline", methods=["GET"])
    async def pipeline_page(self, request: Request):
        """ML pipeline control page."""
        return await self.templates.TemplateResponse(
            "ml_pipeline.html",
            {"request": request},
        )
    
    @expose("/ml-pipeline/run", methods=["POST"])
    async def run_pipeline(self, request: Request):
        """Trigger full ML pipeline rebuild."""
        from app.services.recommendation import run_full_pipeline
        
        db = SessionLocal()
        try:
            result = run_full_pipeline(db)
            # Flash success message
            request.session["flash_message"] = f"✓ Pipeline completed: {result['users_with_vectors']} users, {result['items_with_vectors']} items"
            request.session["flash_type"] = "success"
        except Exception as e:
            request.session["flash_message"] = f"✗ Pipeline failed: {str(e)}"
            request.session["flash_type"] = "error"
        finally:
            db.close()
        
        return RedirectResponse(url="/admin/ml-pipeline", status_code=303)
    
    @expose("/ml-pipeline/update-embeddings", methods=["POST"])
    async def update_embeddings(self, request: Request):
        """Update track content embeddings only (faster than full rebuild)."""
        from app.ml.pipeline import RecommendationPipeline
        
        db = SessionLocal()
        try:
            pipeline = RecommendationPipeline(db)
            tracks_by_id = pipeline._refresh_track_vectors()
            
            request.session["flash_message"] = f"✓ Updated {len(tracks_by_id)} track embeddings"
            request.session["flash_type"] = "success"
        except Exception as e:
            request.session["flash_message"] = f"✗ Failed: {str(e)}"
            request.session["flash_type"] = "error"
        finally:
            db.close()
        
        return RedirectResponse(url="/admin/ml-pipeline", status_code=303)
    
    @expose("/ml-pipeline/update-taste-vectors", methods=["POST"])
    async def update_taste_vectors(self, request: Request):
        """Update user taste vectors only."""
        from app.ml.pipeline import RecommendationPipeline
        
        db = SessionLocal()
        try:
            pipeline = RecommendationPipeline(db)
            # First refresh tracks (needed for taste computation)
            pipeline._refresh_track_vectors()
            count = pipeline._update_user_taste_vectors()
            
            request.session["flash_message"] = f"✓ Updated {count} user taste vectors"
            request.session["flash_type"] = "success"
        except Exception as e:
            request.session["flash_message"] = f"✗ Failed: {str(e)}"
            request.session["flash_type"] = "error"
        finally:
            db.close()
        
        return RedirectResponse(url="/admin/ml-pipeline", status_code=303)


class UserProfilerView(BaseView):
    """
    User profiler — inspect taste vectors, top genres/artists, recommendations.
    """
    
    name = "پروفایل کاربر"
    icon = "fa-solid fa-user-circle"
    
    @expose("/user-profiler", methods=["GET"])
    async def profiler_form(self, request: Request):
        """User profiler search form."""
        user_id = request.query_params.get("user_id")
        
        if not user_id:
            return await self.templates.TemplateResponse(
                "user_profiler.html",
                {"request": request, "profile": None},
            )
        
        # Fetch user profile
        from app.services.recommendation import get_user_profile_debug
        
        db = SessionLocal()
        try:
            profile = get_user_profile_debug(db, int(user_id))
            
            return await self.templates.TemplateResponse(
                "user_profiler.html",
                {"request": request, "profile": profile, "user_id": user_id},
            )
        finally:
            db.close()
