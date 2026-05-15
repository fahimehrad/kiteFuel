#!/bin/sh
set -e

echo "[startup] Waiting for database to be ready..."
python3 - <<'PYEOF'
import os, sys, time

url = os.environ.get("DATABASE_URL", "")
if not url:
    print("[startup] No DATABASE_URL found, skipping wait")
    sys.exit(0)

# SQLAlchemy 2.0 requires postgresql://, not postgres://
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)

import psycopg2
for attempt in range(20):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print(f"[startup] Database ready after {attempt + 1} attempt(s)")
        sys.exit(0)
    except Exception as e:
        print(f"[startup] Attempt {attempt + 1}/20: {e}")
        time.sleep(3)

print("[startup] WARNING: database still not ready after 60s, proceeding anyway")
PYEOF

# ── Kite Passport setup ───────────────────────────────────────────────────────
if [ -n "$KPASS_CONFIG_JSON" ]; then
    mkdir -p .kpass
    echo "$KPASS_CONFIG_JSON"  > .kpass/config.json
    echo "$KPASS_AGENT_JSON"   > .kpass/agent.json
    echo "[startup] Kite Passport config written"
fi

echo "[startup] Running database migrations..."
# stamp base first so alembic always re-applies from scratch on a fresh DB
# (handles stale alembic_version rows from previous failed deploys)
alembic stamp base
alembic upgrade head

echo "[startup] Migrations complete. Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 2
