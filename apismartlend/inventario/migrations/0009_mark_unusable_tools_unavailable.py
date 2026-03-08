from django.db import migrations


ESTADOS_NO_USABLES = ['Defectuoso', 'Dañado']


def marcar_no_usables_no_disponibles(apps, schema_editor):
    HerramientaIndividual = apps.get_model('inventario', 'herramienta_individual')
    TipoHerramienta = apps.get_model('inventario', 'tipo_herramienta')

    HerramientaIndividual.objects.filter(
        estado_herramienta__in=ESTADOS_NO_USABLES,
    ).update(disponible=False)

    for tipo in TipoHerramienta.objects.all().iterator():
        disponibles = HerramientaIndividual.objects.filter(
            id_tipo_herramienta_id=tipo.id_tipo_herramienta,
            disponible=True,
        ).exclude(
            estado_herramienta__in=ESTADOS_NO_USABLES,
        ).count()
        nuevo_stock = max(disponibles - (tipo.reservado or 0), 0)
        TipoHerramienta.objects.filter(pk=tipo.pk).update(stock=nuevo_stock)


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0008_herramienta_individual_disponible_and_more'),
    ]

    operations = [
        migrations.RunPython(
            marcar_no_usables_no_disponibles,
            migrations.RunPython.noop,
        ),
    ]
