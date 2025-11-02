from rest_framework import viewsets

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


class TipoHerramientaViewSet(viewsets.ModelViewSet):
    queryset = tipo_herramienta.objects.all()
    serializer_class = TipoHerramientaSerializer


class CategoriaHerramientaViewSet(viewsets.ModelViewSet):
    queryset = categoria_herramienta.objects.all()
    serializer_class = CategoriaHerramientaSerializer


class HerramientaIndividualViewSet(viewsets.ModelViewSet):
    queryset = herramienta_individual.objects.all()
    serializer_class = HerramientaIndividualSerializer
