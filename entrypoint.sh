#!/bin/bash
set -e

echo "🚀 Starting Logit Server..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h "${POSTGRES_SERVER}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" > /dev/null 2>&1; do
    echo "   PostgreSQL is unavailable - sleeping"
    sleep 1
done
echo "✅ PostgreSQL is ready!"

# Wait for Qdrant to be ready
echo "⏳ Waiting for Qdrant..."
QDRANT_URL="http://${QDRANT_HOST}:${QDRANT_PORT}/healthz"
until curl -f -s "$QDRANT_URL" > /dev/null 2>&1; do
    echo "   Qdrant is unavailable - sleeping"
    sleep 1
done
echo "✅ Qdrant is ready!"

# Run Alembic migrations
echo "🔄 Running database migrations..."
alembic upgrade head
echo "✅ Migrations completed!"

# Start the application
echo "🎉 Starting FastAPI application..."
exec "$@"
