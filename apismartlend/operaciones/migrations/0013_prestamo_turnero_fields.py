from django.db import migrations, models


def poblar_estado_turno(apps, schema_editor):
    Prestamo = apps.get_model('operaciones', 'prestamo')
    Prestamo.objects.filter(estado_prestamo='Pendiente').update(estado_turno_pantalla='EnCola')
    Prestamo.objects.exclude(estado_prestamo='Pendiente').update(estado_turno_pantalla='FueraDeCola')


class Migration(migrations.Migration):

    dependencies = [
        ('operaciones', '0012_delete_reserva'),
    ]

    operations = [
        migrations.AddField(
            model_name='prestamo',
            name='estado_turno_pantalla',
            field=models.CharField(
                choices=[
                    ('EnCola', 'En cola'),
                    ('Mostrado', 'Mostrado'),
                    ('Saltado', 'Saltado'),
                    ('FueraDeCola', 'Fuera de cola'),
                ],
                default='EnCola',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='prestamo',
            name='turno_mostrado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='prestamo',
            name='turno_veces_mostrado',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(poblar_estado_turno, migrations.RunPython.noop),
    ]
