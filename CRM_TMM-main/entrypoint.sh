#!/bin/sh
set -e

echo "=== Entrypoint: waiting for DB and applying migrations ==="
retries=0
until python manage.py migrate --noinput; do
  retries=$((retries+1))
  if [ "$retries" -ge 30 ]; then
    echo "Migrations failed after $retries attempts" >&2
    exit 1
  fi
  echo "Database unavailable - sleeping 1s"
  sleep 1
done

echo "=== Creating superuser (if env vars provided) ==="
if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_EMAIL}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
  echo "Creating superuser ${DJANGO_SUPERUSER_USERNAME}..."
  # Use a heredoc to run a small Python script safely (avoids quoting issues)
  python - <<'PY'
import os
import sys
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tmm_project.settings')
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    User = get_user_model()
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username, email, password)
        print('Superuser created')
    else:
        print('Superuser already exists')
except Exception as e:
    print('Failed to create superuser:', e, file=sys.stderr)
    # Continue even if superuser creation fails
PY
else
  echo "DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD not set - skipping superuser creation"
fi

echo "=== Running optional data population ==="
if [ "${POPULATE_DATA:-}" = "1" ] || [ "${POPULATE_DATA:-}" = "true" ]; then
  echo "POPULATE_DATA enabled - running populate script"
  # Check if there is already data in key models; if so, skip populate
  echo "Checking whether DB already has data..."
  HAS_DATA=$(python - <<'PY'
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tmm_project.settings')
try:
    import django
    django.setup()
    from crm.models import Cliente, Producto, Empresa, Taller
    exists = Cliente.objects.exists() or Producto.objects.exists() or Empresa.objects.exists() or Taller.objects.exists()
    print('1' if exists else '0')
except Exception as e:
    # If the check fails, print 0 to be safe and allow populate to run
    print('0')
PY
)

  if [ "$HAS_DATA" = "1" ]; then
    echo "Existing data found in DB — skipping populate script."
  else
    echo "No existing data found — running populate script"
    # The script configures Django itself, so run it directly
    python crm/populate_data.py || echo "populate script failed (continuing)"
  fi
else
  echo "POPULATE_DATA not set - skipping populate script"
fi

echo "=== Entrypoint finished, executing CMD ==="
exec "$@"
