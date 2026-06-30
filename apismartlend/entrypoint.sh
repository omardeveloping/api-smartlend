#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-appuser}"
APP_GROUP="${APP_GROUP:-appuser}"

run_cmd_as_appuser() {
  if [[ "$(id -u)" -eq 0 ]]; then
    gosu "${APP_USER}:${APP_GROUP}" "$@"
  else
    "$@"
  fi
}

exec_as_appuser() {
  if [[ "$(id -u)" -eq 0 ]]; then
    exec gosu "${APP_USER}:${APP_GROUP}" "$@"
  else
    exec "$@"
  fi
}

ensure_runtime_permissions() {
  local target
  for target in /app/media /app/media/tipos_herramienta /app/media/herramientas /app/staticfiles; do
    mkdir -p "$target"
  done

  if [[ "$(id -u)" -eq 0 ]]; then
    chown -R "${APP_USER}:${APP_GROUP}" /app/media /app/staticfiles || true
  fi

  chmod -R ug+rwX /app/media /app/staticfiles || true

  for target in /app/media /app/media/tipos_herramienta /app/media/herramientas /app/staticfiles; do
    if ! run_cmd_as_appuser test -w "$target"; then
      echo "Error: ${target} no es escribible por ${APP_USER}. Revisa permisos del volumen montado." >&2
      exit 1
    fi
  done
}

ensure_runtime_permissions

# Wait for database DNS/port before running migrations
echo "Waiting for database ${DATABASE_HOST:-db}:${DATABASE_PORT:-5432}..."
until run_cmd_as_appuser python - <<'PYCODE'
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
run_cmd_as_appuser python manage.py migrate --noinput

cmd="${1:-}"

# Si el comando solicitado es celery (worker/beat), ejecútalo directamente
if [[ "$cmd" == "celery" ]]; then
  shift
  exec_as_appuser celery "$@"
fi

# Si no hay comando (servicio web) o es gunicorn, recopila estáticos y arranca web
if [[ -z "$cmd" || "$cmd" == "gunicorn" ]]; then
  run_cmd_as_appuser python manage.py collectstatic --noinput
  exec_as_appuser gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 180 apismartlend.wsgi:application
fi

# Para cualquier otro comando, simplemente ejecútalo
exec_as_appuser "$@"
