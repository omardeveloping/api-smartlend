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
    serializer_class = HerramientaIndividualSerializer
    queryset = herramienta_individual.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        tipo_id = self.request.query_params.get('id_tipo_herramienta')
        if tipo_id:
            try:
                qs = qs.filter(id_tipo_herramienta_id=int(tipo_id))
            except ValueError:
                pass
        return qs
