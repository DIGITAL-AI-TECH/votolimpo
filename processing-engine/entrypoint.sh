#!/bin/sh
set -e

# The app (FastAPI/asyncpg) connects using individual DB_* env vars directly,
# avoiding URL-encoding issues with special characters in passwords.
# Alembic (SQLAlchemy) still needs a DATABASE_URL, so we build it here
# with proper URL-encoding of the password.

if [ -z "${DATABASE_URL}" ] && [ -n "${DB_PASSWORD}" ]; then
    ENCODED_PW=$(python -c "import urllib.parse, os; print(urllib.parse.quote(os.environ['DB_PASSWORD'], safe=''))")
    export DATABASE_URL="postgresql://${DB_USER:-postgres}:${ENCODED_PW}@${DB_HOST:-postgres}:${DB_PORT:-5432}/${DB_NAME:-processing_engine}"
    echo "DATABASE_URL constructed for Alembic (password URL-encoded)."
fi

echo "Running database migrations..."
MAX_RETRIES=30
RETRY_INTERVAL=2
for i in $(seq 1 $MAX_RETRIES); do
    if python -m alembic upgrade head 2>&1; then
        echo "Migrations completed successfully."
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "ERROR: Migrations failed after $MAX_RETRIES retries. Exiting."
        exit 1
    fi
    echo "Migration attempt $i/$MAX_RETRIES failed. Retrying in ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
