#!/bin/sh

# The app (FastAPI/asyncpg) connects using individual DB_* env vars directly.
# Alembic also uses individual params via connect_args (alembic/env.py).
# No DATABASE_URL construction needed — avoids shell/URL encoding issues.

echo "=== Processing Engine entrypoint starting ==="
echo "Python: $(python --version 2>&1)"
echo "Working dir: $(pwd)"

# Debug: print connection info (password hashed, never plaintext)
python -c '
import os, hashlib
pw = os.environ.get("DB_PASSWORD", "")
h = hashlib.md5(pw.encode()).hexdigest()
host = os.environ.get("DB_HOST", "?")
port = os.environ.get("DB_PORT", "?")
db = os.environ.get("DB_NAME", "?")
user = os.environ.get("DB_USER", "?")
has_url = bool(os.environ.get("DATABASE_URL"))
print(f"DB connection: host={host}, port={port}, db={db}, user={user}, pw_len={len(pw)}, pw_md5={h}")
print(f"DATABASE_URL set: {has_url}")
' || echo "WARNING: debug print failed (non-fatal)"

# Smoke test: verify critical imports work
echo "Verifying imports..."
python -c 'import fastapi; import asyncpg; import uvicorn; import alembic; print("All critical imports OK")' || {
    echo "FATAL: Critical import failed. Container cannot start."
    exit 1
}

echo "Running database migrations..."
MAX_RETRIES=30
RETRY_INTERVAL=2
MIGRATION_OK=false
for i in $(seq 1 $MAX_RETRIES); do
    if python -m alembic upgrade head 2>&1; then
        echo "Migrations completed successfully."
        MIGRATION_OK=true
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "ERROR: Migrations failed after $MAX_RETRIES retries."
        break
    fi
    echo "Migration attempt $i/$MAX_RETRIES failed. Retrying in ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done

if [ "$MIGRATION_OK" = "false" ]; then
    echo "WARNING: Migrations did not complete. Starting uvicorn anyway (health check will report degraded)."
fi

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
