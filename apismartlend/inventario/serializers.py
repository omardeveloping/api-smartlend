from rest_framework import serializers

from .models import (
    categoria_herramienta,
    estado_herramienta,
    herramienta,
)


class EstadoHerramientaSerializer(serializers.ModelSerializer):
    class Meta:
        model = estado_herramienta
        fields = '__all__'


class CategoriaHerramientaSerializer(serializers.ModelSerializer):
    class Meta:
        model = categoria_herramienta
        fields = '__all__'


class HerramientaSerializer(serializers.ModelSerializer):
    class Meta:
        model = herramienta
        fields = '__all__'
