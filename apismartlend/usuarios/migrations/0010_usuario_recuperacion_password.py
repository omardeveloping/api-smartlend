from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0009_rol_usuarios_codigo'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='codigo_recuperacion_expira',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='codigo_recuperacion_hash',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]
