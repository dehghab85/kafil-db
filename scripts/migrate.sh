#!/bin/bash
# Database migration helper — creates/applies Alembic migrations.

set -e

echo "=== Kafil Music Migration Tool ==="

if [ "$1" = "create" ]; then
    if [ -z "$2" ]; then
        echo "Usage: ./scripts/migrate.sh create 'migration message'"
        exit 1
    fi
    echo "Creating new migration: $2"
    alembic revision --autogenerate -m "$2"

elif [ "$1" = "upgrade" ]; then
    echo "Applying migrations..."
    alembic upgrade head
    echo "✓ Database is up to date"

elif [ "$1" = "downgrade" ]; then
    echo "Rolling back one migration..."
    alembic downgrade -1

elif [ "$1" = "history" ]; then
    alembic history

else
    echo "Usage:"
    echo "  ./scripts/migrate.sh create 'add_column_xyz'   # Create new migration"
    echo "  ./scripts/migrate.sh upgrade                   # Apply all pending"
    echo "  ./scripts/migrate.sh downgrade                 # Rollback one step"
    echo "  ./scripts/migrate.sh history                   # Show migration log"
fi
