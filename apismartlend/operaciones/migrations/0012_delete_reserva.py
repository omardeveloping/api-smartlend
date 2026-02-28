from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('operaciones', '0011_alerta_archivada'),
    ]

    operations = [
        migrations.DeleteModel(
            name='reserva',
        ),
    ]
