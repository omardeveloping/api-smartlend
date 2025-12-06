# Generated manually to add codigo to prestamo
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('operaciones', '0006_alerta_criticidad'),
    ]

    operations = [
        migrations.AddField(
            model_name='prestamo',
            name='codigo',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
