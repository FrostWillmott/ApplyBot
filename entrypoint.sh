#!/usr/bin/env bash
set -e

# Wait for database to be ready
echo ">>> Waiting for database..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo ">>> Database is ready!"

# Wait for Redis to be ready
echo ">>> Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 0.1
done
echo ">>> Redis is ready!"

# Apply database migrations
echo ">>> Applying migrations..."
alembic upgrade head || echo ">>> Migrations failed or not configured yet"

# Start the application
echo ">>> Starting application..."
exec "$@"