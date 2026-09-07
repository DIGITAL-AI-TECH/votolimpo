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

# Pre-flight: test PG connection from this container
echo "--- Pre-flight PG connection test ---"
python -c '
import asyncio, asyncpg, os, hashlib
async def test():
    pw = os.environ.get("DB_PASSWORD", "")
    h = os.environ.get("DB_HOST", "localhost")
    p = int(os.environ.get("DB_PORT", "5432"))
    u = os.environ.get("DB_USER", "postgres")
    d = os.environ.get("DB_NAME", "processing_engine")
    md5 = hashlib.md5(pw.encode()).hexdigest()
    print(f"Preflight: host={h}, port={p}, user={u}, db={d}, pw_len={len(pw)}, pw_md5={md5}")
    try:
        conn = await asyncpg.connect(host=h, port=p, user=u, password=pw, database=d, timeout=15)
        ver = await conn.fetchval("SELECT version()")
        print(f"Preflight: CONNECTED OK — {ver[:50]}")
        await conn.close()
    except Exception as e:
        print(f"Preflight: FAILED — {type(e).__name__}: {e}")
        # Try with explicit password string to rule out env var encoding issues
        try:
            conn2 = await asyncpg.connect(host=h, port=p, user=u, password=pw.strip(), database=d, timeout=10)
            print("Preflight: CONNECTED OK with stripped password!")
            await conn2.close()
        except Exception as e2:
            print(f"Preflight: Also failed with stripped pw — {type(e2).__name__}")
            # Show hex of first/last 4 bytes of password for debugging
            print(f"Preflight: pw hex start={pw[:4].encode().hex()}, end={pw[-4:].encode().hex()}")
asyncio.run(test())
' || echo "WARNING: preflight test script failed (non-fatal)"

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
