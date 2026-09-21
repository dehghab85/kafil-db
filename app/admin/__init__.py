"""
Kafil Music Admin Dashboard — Comprehensive SQLAdmin implementation.

Features:
  - CRUD views for all models (User, Track, Artist, Genre, Playlist, Interaction)
  - Custom dashboard with statistics and charts
  - ML Pipeline control panel
  - File upload support for track covers
  - Advanced search, filters, and relationships
  - Professional dark-mode theme
"""
from app.admin.auth import AdminAuth
from app.admin.setup import setup_admin

__all__ = ["setup_admin", "AdminAuth"]
