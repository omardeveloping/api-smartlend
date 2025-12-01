#!/usr/bin/env bash
set -e

# Wait for database DNS/port before running migrations
echo "Waiting for database ${DATABASE_HOST:-db}:${DATABASE_PORT:-5432}..."
until python - <<'PYCODE'
import os, socket, sys
host = os.environ.get("DATABASE_HOST", "db")
port = int(os.environ.get("DATABASE_PORT", "5432"))
s = socket.socket()
s.settimeout(2)
try:
    s.connect((host, port))
except Exception:
    sys.exit(1)
finally:
    s.close()
PYCODE
do
  echo "Database not ready, sleeping..."
  sleep 2
done

# Aplica migraciones pendientes
python manage.py migrate --noinput

# Recopila estáticos (si necesitas tenerlos locales)
python manage.py collectstatic --noinput

# Lanza Gunicorn con los argumentos que quieras
exec gunicorn --bind 0.0.0.0:8000 --workers 3 apismartlend.wsgi:application
