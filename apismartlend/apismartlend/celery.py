import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apismartlend.settings')

app = Celery('apismartlend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'ban-overdue-prestamos-daily': {
        'task': 'operaciones.tasks.ban_overdue_prestamos',
        'schedule': crontab(hour=0, minute=0),
    },
}

