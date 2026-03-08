from django.db import migrations, models


def poblar_codigo_roles(apps, schema_editor):
    RolUsuarios = apps.get_model('usuarios', 'rol_usuarios')
    for rol in RolUsuarios.objects.all().iterator():
        codigo = (getattr(rol, 'codigo', '') or '').strip()
        if not codigo:
            codigo = (rol.nombre or '').strip()
        RolUsuarios.objects.filter(pk=rol.pk).update(codigo=codigo.upper())


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0008_rename_ban_fields_spanish'),
    ]

    operations = [
        migrations.AddField(
            model_name='rol_usuarios',
            name='codigo',
            field=models.CharField(blank=True, db_index=True, default='', max_length=30),
        ),
        migrations.RunPython(poblar_codigo_roles, migrations.RunPython.noop),
    ]
