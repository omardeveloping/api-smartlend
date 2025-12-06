# Generated manually for criticidad en alertas
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('operaciones', '0005_alerta'),
    ]

    operations = [
        migrations.AddField(
            model_name='alerta',
            name='criticidad',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
