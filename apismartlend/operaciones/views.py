from rest_framework import viewsets

from .models import (
    prestamo,
    reserva,
)
from .serializers import (
    PrestamoSerializer,
    ReservaSerializer,
)

class ReservaViewSet(viewsets.ModelViewSet):
    queryset = reserva.objects.all()
    serializer_class = ReservaSerializer


class PrestamoViewSet(viewsets.ModelViewSet):
    queryset = prestamo.objects.all()
    serializer_class = PrestamoSerializer
