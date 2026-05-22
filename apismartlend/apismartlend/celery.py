import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apismartlend.settings')

app = Celery('apismartlend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'reconciliar-pendientes-expirados-cada-5-minutos': {
        'task': 'operaciones.tasks.reconciliar_prestamos_pendientes_expirados',
        'schedule': crontab(minute='*/5'),
    },
    'ban-overdue-prestamos-daily': {
        'task': 'operaciones.tasks.ban_overdue_prestamos',
        'schedule': crontab(hour=0, minute=0),
    },
    'verificar-mantenciones-diarias': {
        'task': 'operaciones.tasks.verificar_mantenciones_proximas',
        'schedule': crontab(hour=8, minute=0),
    },
}
