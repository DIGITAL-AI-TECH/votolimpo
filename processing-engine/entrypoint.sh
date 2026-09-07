#!/bin/sh
set -e

echo "Running database migrations..."
# Retry loop: wait for PostgreSQL to be ready before running migrations
MAX_RETRIES=30
RETRY_INTERVAL=2
for i in $(seq 1 $MAX_RETRIES); do
    if alembic upgrade head 2>&1; then
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
