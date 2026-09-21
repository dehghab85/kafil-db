#!/usr/bin/env python3
"""
Manual pipeline runner — triggers full ML pipeline rebuild.

Usage:
    python scripts/run_pipeline.py
"""
from app.config import get_settings
from app.db import SessionLocal
from app.services.recommendation import run_full_pipeline

settings = get_settings()


def main():
    print("=== Kafil Music ML Pipeline ===")
    print(f"Database: {settings.database_url}")
    print(f"Artifact dir: {settings.artifact_dir}")
    print("\nStarting full pipeline rebuild...\n")

    db = SessionLocal()
    try:
        result = run_full_pipeline(db)
        print("\n✓ Pipeline completed successfully!")
        print(f"  Users with vectors: {result['users_with_vectors']}")
        print(f"  Items with vectors: {result['items_with_vectors']}")
        print(f"  Total tracks: {result['total_tracks']}")
    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
