from rest_framework import viewsets

from .models import (
    estado_devolucion,
    estado_prestamo,
    estado_reserva,
    prestamo,
    reserva,
)
from .serializers import (
    EstadoDevolucionSerializer,
    EstadoPrestamoSerializer,
    EstadoReservaSerializer,
    PrestamoSerializer,
    ReservaSerializer,
)


class EstadoReservaViewSet(viewsets.ModelViewSet):
    queryset = estado_reserva.objects.all()
    serializer_class = EstadoReservaSerializer


class EstadoPrestamoViewSet(viewsets.ModelViewSet):
    queryset = estado_prestamo.objects.all()
    serializer_class = EstadoPrestamoSerializer


class EstadoDevolucionViewSet(viewsets.ModelViewSet):
    queryset = estado_devolucion.objects.all()
    serializer_class = EstadoDevolucionSerializer


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = reserva.objects.all()
    serializer_class = ReservaSerializer


class PrestamoViewSet(viewsets.ModelViewSet):
    queryset = prestamo.objects.all()
    serializer_class = PrestamoSerializer
