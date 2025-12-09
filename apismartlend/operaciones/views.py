from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    alerta,
    prestamo,
    reserva,
)
from .serializers import (
    AlertaSerializer,
    PrestamoSerializer,
    ReservaSerializer,
)


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = reserva.objects.all()
    serializer_class = ReservaSerializer


class PrestamoViewSet(viewsets.ModelViewSet):
    queryset = prestamo.objects.all().prefetch_related(
        'herramientas',
        'herramientas__id_tipo_herramienta',
    )
    serializer_class = PrestamoSerializer

    @action(detail=False, methods=['get'])
    def vencidos(self, request):
        now = timezone.now()
        vencidos = self.get_queryset().filter(
            fecha_devolucion_real__isnull=True,
            fecha_devolucion_esperada__lt=now,
        )
        serializer = self.get_serializer(vencidos, many=True)
        return Response(serializer.data)


class AlertasViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertaSerializer

    def get_queryset(self):
        qs = alerta.objects.all()
        # Optional: filter only unresolved alerts with ?solo_pendientes=true
        if self.request.query_params.get('solo_pendientes') == 'true':
            qs = qs.filter(resuelta=False)
        return qs

    def list(self, request, *args, **kwargs):
        now = timezone.now()
        vencidos = prestamo.objects.filter(
            fecha_devolucion_real__isnull=True,
            fecha_devolucion_esperada__lt=now,
        )

        for loan in vencidos:
            alert, created = alerta.objects.get_or_create(
                prestamo=loan,
                defaults={'mensaje': 'Prestamo vencido'},
            )
            if alert.resuelta:
                alert.resuelta = False
                alert.resuelta_en = None
                alert.save(update_fields=['resuelta', 'resuelta_en'])

        alerta.objects.filter(
            resuelta=False,
        ).exclude(
            prestamo__fecha_devolucion_real__isnull=True,
            prestamo__fecha_devolucion_esperada__lt=now,
        ).update(resuelta=True, resuelta_en=now)

        return super().list(request, *args, **kwargs)
