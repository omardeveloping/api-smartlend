#!/bin/sh
set -e

# Aplica migraciones pendientes
python manage.py migrate --noinput

# Recopila estáticos (si necesitas tenerlos locales)
python manage.py collectstatic --noinput

# Lanza Gunicorn con los argumentos que quieras
exec gunicorn --bind 0.0.0.0:8000 --workers 3 apismartlend.wsgi:application
