from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Sum, When
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from operaciones.models import prestamo

from .models import (
    categoria_herramienta,
    tipo_herramienta,
    herramienta_individual,
)
from .serializers import (
    CategoriaHerramientaSerializer,
    TipoHerramientaSerializer,
    HerramientaIndividualSerializer,
)


def _annotate_with_prestamo_estado(queryset):
    """
    Marca cada herramienta con un flag booleano si está asociada a un préstamo
    que sigue abierto (sin fecha de devolución y no cancelado/finalizado).
    """
    prestamos_activos = prestamo.objects.filter(
        fecha_devolucion_real__isnull=True,
    ).exclude(
        estado_prestamo__in=[
            prestamo.EstadoPrestamo.FINALIZADO,
            prestamo.EstadoPrestamo.CANCELADO,
        ]
    )
    return queryset.annotate(
        esta_en_prestamo_activo=Exists(
            prestamos_activos.filter(
                Q(herramientas__pk=OuterRef('pk'))
                | Q(id_herramienta_individual_id=OuterRef('pk'))
            )
        )
    )


class TipoHerramientaViewSet(viewsets.ModelViewSet):
    queryset = tipo_herramienta.objects.all()
    serializer_class = TipoHerramientaSerializer

    @action(detail=False, methods=['get'], url_path='resumen')
    def resumen_herramientas(self, request):
        herramientas_annotated = _annotate_with_prestamo_estado(
            herramienta_individual.objects.all()
        )
        resumen = (
            herramientas_annotated.values('id_tipo_herramienta')
            .annotate(
                total_herramientas=Count('id_herramienta', distinct=True),
                herramientas_disponibles=Sum(
                    Case(
                        When(esta_en_prestamo_activo=False, then=1),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
            )
        )
        totales_por_tipo = {
            item['id_tipo_herramienta']: {
                'total_herramientas': item.get('total_herramientas') or 0,
                'herramientas_disponibles': item.get('herramientas_disponibles') or 0,
            }
            for item in resumen
        }

        data = []
        for tipo in self.get_queryset().order_by('nombre'):
            cantidades = totales_por_tipo.get(tipo.id_tipo_herramienta, {})
            data.append(
                {
                    'id_tipo_herramienta': tipo.id_tipo_herramienta,
                    'nombre': tipo.nombre,
                    'descripcion': tipo.descripcion,
                    'imagen': tipo.imagen.url if tipo.imagen else None,
                    'total_herramientas': cantidades.get('total_herramientas', 0),
                    'herramientas_disponibles': cantidades.get('herramientas_disponibles', 0),
                }
            )
        return Response(data)


class CategoriaHerramientaViewSet(viewsets.ModelViewSet):
    queryset = categoria_herramienta.objects.all()
    serializer_class = CategoriaHerramientaSerializer


class HerramientaIndividualViewSet(viewsets.ModelViewSet):
    serializer_class = HerramientaIndividualSerializer
    queryset = herramienta_individual.objects.all()

    def get_queryset(self):
        qs = _annotate_with_prestamo_estado(super().get_queryset())
        tipo_id = self.request.query_params.get('id_tipo_herramienta')
        if tipo_id:
            try:
                qs = qs.filter(id_tipo_herramienta_id=int(tipo_id))
            except ValueError:
                pass
        if self.request.query_params.get('solo_disponibles') == 'true':
            qs = qs.filter(esta_en_prestamo_activo=False)
        return qs
