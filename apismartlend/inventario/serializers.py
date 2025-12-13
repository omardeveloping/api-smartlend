from rest_framework import serializers

from .models import (
    categoria_herramienta,
    tipo_herramienta,
    herramienta_individual,
    historial_herramienta,
)


class TipoHerramientaSerializer(serializers.ModelSerializer):
    class Meta:
        model = tipo_herramienta
        fields = '__all__'


class CategoriaHerramientaSerializer(serializers.ModelSerializer):
    class Meta:
        model = categoria_herramienta
        fields = '__all__'


class HerramientaIndividualSerializer(serializers.ModelSerializer):
    class Meta:
        model = herramienta_individual
        fields = '__all__'


class HistorialHerramientaSerializer(serializers.ModelSerializer):
    herramienta_detalle = HerramientaIndividualSerializer(source='herramienta', read_only=True)

    class Meta:
        model = historial_herramienta
        fields = [
            'id_historial',
            'herramienta',
            'herramienta_detalle',
            'estado_herramienta',
            'registrada_en',
            'prestamo',
            'usuario',
        ]
