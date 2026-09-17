#!/usr/bin/env bash
set -e

# Wait for Postgres to accept connections (robust across compose v1/v2/dockge).
echo "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
python - <<'PY'
import os, time, sys
import psycopg2
for i in range(60):
    try:
        psycopg2.connect(
            host=os.environ["POSTGRES_HOST"], port=os.environ.get("POSTGRES_PORT", "5432"),
            user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
            dbname=os.environ["POSTGRES_DB"],
        ).close()
        print("Postgres is up."); sys.exit(0)
    except Exception as e:
        print(f"  ...not ready ({e.__class__.__name__}), retry {i+1}/60"); time.sleep(2)
print("Postgres did not become ready in time.", file=sys.stderr); sys.exit(1)
PY

echo "Running migrations..."
alembic upgrade head

echo "Seeding admin (idempotent)..."
python -m scripts.seed_admin || echo "seed_admin skipped/failed (non-fatal)"

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
