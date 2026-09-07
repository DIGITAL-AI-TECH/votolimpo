#!/bin/sh
set -e

# The app (FastAPI/asyncpg) connects using individual DB_* env vars directly,
# avoiding URL-encoding issues with special characters in passwords.
#
# Alembic (SQLAlchemy) builds DATABASE_URL internally in alembic/env.py
# using urllib.parse.quote — no shell interpolation of the password.
# We do NOT set DATABASE_URL here to avoid shell mangling special chars.

# Debug: print password hash (not the password itself) to verify what we received
python -c "
import os, hashlib
pw = os.environ.get('DB_PASSWORD', '')
h = hashlib.md5(pw.encode()).hexdigest()
print(f'DB connection: host={os.environ.get(\"DB_HOST\",\"?\")}, port={os.environ.get(\"DB_PORT\",\"?\")}, db={os.environ.get(\"DB_NAME\",\"?\")}, user={os.environ.get(\"DB_USER\",\"?\")}, pw_len={len(pw)}, pw_md5={h}')
print(f'DATABASE_URL set: {bool(os.environ.get(\"DATABASE_URL\"))}')
"

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
