from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0006_alter_tipo_herramienta_imagen_url'),
    ]

    operations = [
        migrations.RenameField(
            model_name='tipo_herramienta',
            old_name='imagen_url',
            new_name='imagen',
        ),
    ]
