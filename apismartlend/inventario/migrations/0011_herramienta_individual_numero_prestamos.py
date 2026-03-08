from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0010_add_marca_modelo_to_herramienta_individual'),
    ]

    operations = [
        migrations.AddField(
            model_name='herramienta_individual',
            name='numero_prestamos',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
    ]
