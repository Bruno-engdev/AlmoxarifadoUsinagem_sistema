#!/bin/sh
# Container entrypoint: apply migrations, seed defaults, then start the web server.
#
# Behaviour is controlled by env vars:
#   RUN_MIGRATIONS=1 (default 1)  -> alembic upgrade head
#   RUN_SEED=1       (default 1)  -> python -m app.cli seed
#   AUTO_BOOTSTRAP   (unset)      -> set to 1 to enable in-process SQLite bootstrap
#                                    (useful only when DATABASE_URL points to SQLite
#                                     and Alembic is intentionally bypassed)
set -eu

: "${RUN_MIGRATIONS:=1}"
: "${RUN_SEED:=1}"

if [ "$RUN_MIGRATIONS" = "1" ]; then
    echo "[entrypoint] Running Alembic migrations..."
    alembic upgrade head
fi

if [ "$RUN_SEED" = "1" ]; then
    echo "[entrypoint] Seeding defaults and admin..."
    python -m app.cli seed
fi

echo "[entrypoint] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
