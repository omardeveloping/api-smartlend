from rest_framework import viewsets

from .models import (
    categoria_herramienta,
    estado_herramienta,
    herramienta,
)
from .serializers import (
    CategoriaHerramientaSerializer,
    EstadoHerramientaSerializer,
    HerramientaSerializer,
)


class EstadoHerramientaViewSet(viewsets.ModelViewSet):
    queryset = estado_herramienta.objects.all()
    serializer_class = EstadoHerramientaSerializer


class CategoriaHerramientaViewSet(viewsets.ModelViewSet):
    queryset = categoria_herramienta.objects.all()
    serializer_class = CategoriaHerramientaSerializer


class HerramientaViewSet(viewsets.ModelViewSet):
    queryset = herramienta.objects.all()
    serializer_class = HerramientaSerializer
