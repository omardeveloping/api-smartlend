from rest_framework import serializers

from .models import (
    categoria_herramienta,
    tipo_herramienta,
    herramienta_individual,
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
