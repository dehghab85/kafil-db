"""initial schema + pgvector extension

Revision ID: 001
Revises: 
Create Date: 2026-09-15 12:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (PostgreSQL only)
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Artists
    op.create_table(
        'artists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_artists_name'), 'artists', ['name'], unique=True)

    # Albums
    op.create_table(
        'albums',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('artist_id', sa.Integer(), nullable=False),
        sa.Column('release_date', sa.DateTime(), nullable=True),
        sa.Column('cover_url', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['artist_id'], ['artists.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Genres
    op.create_table(
        'genres',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_genres_name'), 'genres', ['name'], unique=True)

    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=True),
        # phone_number is nullable here to match the ORM model (username/password users
        # can register without a phone; OTP-based users get their phone populated).
        sa.Column('phone_number', sa.String(length=15), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('password_hash', sa.String(length=128), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_phone_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        # Taste vector (pgvector on postgres, JSON on sqlite)
        sa.Column('taste_vector', sa.Text(), nullable=True),
        sa.Column('preferred_genre_ids', sa.Text(), nullable=True),
        sa.Column('preferred_artist_ids', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_phone_number'), 'users', ['phone_number'], unique=True)

    # Tracks
    op.create_table(
        'tracks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('artist_id', sa.Integer(), nullable=False),
        sa.Column('album_id', sa.Integer(), nullable=True),
        sa.Column('audio_url', sa.String(length=500), nullable=False),
        sa.Column('cover_url', sa.String(length=500), nullable=True),
        sa.Column('duration_sec', sa.Integer(), default=0),
        sa.Column('release_date', sa.DateTime(), nullable=True),
        sa.Column('lyrics', sa.Text(), nullable=True),
        sa.Column('lyrics_timestamps', sa.Text(), nullable=True),
        sa.Column('view_count', sa.Integer(), default=0, nullable=False),
        sa.Column('like_count', sa.Integer(), default=0, nullable=False),
        sa.Column('skip_count', sa.Integer(), default=0, nullable=False),
        sa.Column('audio_features', sa.Text(), nullable=True),  # JSON
        # Content vector (pgvector on postgres, JSON on sqlite)
        sa.Column('content_vector', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['artist_id'], ['artists.id'], ),
        sa.ForeignKeyConstraint(['album_id'], ['albums.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tracks_title'), 'tracks', ['title'])
    op.create_index(op.f('ix_tracks_artist_id'), 'tracks', ['artist_id'])
    op.create_index('ix_track_artist_title', 'tracks', ['artist_id', 'title'])

    # Track-Genre M2M
    op.create_table(
        'track_genres',
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('genre_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['genre_id'], ['genres.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('track_id', 'genre_id')
    )

    # User Favorites M2M
    op.create_table(
        'user_favorites',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'track_id')
    )

    # User Interactions
    op.create_table(
        'user_interactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=True),
        sa.Column('interaction_type', sa.String(length=20), nullable=False),
        sa.Column('listen_duration', sa.Integer(), default=0),
        sa.Column('search_query', sa.String(length=200), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('weight', sa.Float(), default=0.0, nullable=False),
        # Context vector snapshot (optional)
        sa.Column('context_vector', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_interactions_user_id'), 'user_interactions', ['user_id'])
    op.create_index(op.f('ix_user_interactions_track_id'), 'user_interactions', ['track_id'])
    op.create_index(op.f('ix_user_interactions_interaction_type'), 'user_interactions', ['interaction_type'])
    op.create_index(op.f('ix_user_interactions_timestamp'), 'user_interactions', ['timestamp'])
    op.create_index('ix_interaction_user_time', 'user_interactions', ['user_id', 'timestamp'])
    op.create_index('ix_interaction_user_track', 'user_interactions', ['user_id', 'track_id'])

    # Playlists
    op.create_table(
        'playlists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('is_private', sa.Boolean(), default=True),
        sa.Column('is_auto_generated', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Playlist-Track M2M
    op.create_table(
        'playlist_tracks',
        sa.Column('playlist_id', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), default=0),
        sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('playlist_id', 'track_id')
    )

    # OTP Codes
    op.create_table(
        'otp_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=15), nullable=False),
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_otp_codes_phone_number'), 'otp_codes', ['phone_number'])
    op.create_index('ix_otp_phone_expiry', 'otp_codes', ['phone_number', 'expires_at'])


def downgrade() -> None:
    op.drop_table('otp_codes')
    op.drop_table('playlist_tracks')
    op.drop_table('playlists')
    op.drop_table('user_interactions')
    op.drop_table('user_favorites')
    op.drop_table('track_genres')
    op.drop_table('tracks')
    op.drop_table('users')
    op.drop_table('genres')
    op.drop_table('albums')
    op.drop_table('artists')

    # Drop pgvector extension (PostgreSQL only)
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP EXTENSION IF EXISTS vector")
