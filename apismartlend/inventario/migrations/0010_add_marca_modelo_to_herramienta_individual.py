from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0009_mark_unusable_tools_unavailable'),
    ]

    operations = [
        migrations.AddField(
            model_name='herramienta_individual',
            name='marca',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='herramienta_individual',
            name='modelo',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
