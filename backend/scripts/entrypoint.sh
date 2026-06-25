#!/bin/sh
# Container entrypoint: run Alembic migrations on Postgres (schema is owned by
# migrations in prod), then start Gunicorn with Uvicorn workers. The app's
# lifespan seeds the KB on first start. SQLite dev needs no migration step.
set -e

case "$DATABASE_URL" in
  *postgres*)
    echo "[entrypoint] Running Alembic migrations..."
    alembic upgrade head
    ;;
  *)
    echo "[entrypoint] SQLite/dev datastore — skipping migrations (create_all in app)."
    ;;
esac

exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8787 \
  -w "${WEB_CONCURRENCY:-4}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
