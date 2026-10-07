#!/bin/sh
set -eu

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"

python scripts/wait_for_db.py
python manage.py migrate --noinput

if [ "${AUTO_SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo \
    --small \
    --if-empty \
    --seed "${DEMO_SEED:-42}" \
    --reference-date "${DEMO_REFERENCE_DATE:-$(date -u +%F)}"
fi

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
