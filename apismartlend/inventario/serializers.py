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
    usuario_prestador_id = serializers.IntegerField(source='usuario_id', read_only=True)
    usuario_prestador_nombre = serializers.SerializerMethodField()
    usuario_prestador_rut = serializers.SerializerMethodField()
    usuario_receptor_id = serializers.IntegerField(source='prestamo.id_usuario_id', read_only=True)
    usuario_receptor_nombre = serializers.SerializerMethodField()
    usuario_receptor_rut = serializers.SerializerMethodField()

    def get_usuario_prestador_nombre(self, obj):
        if not obj.usuario:
            return None
        nombres = (getattr(obj.usuario, 'nombres', '') or '').strip()
        apellidos = (getattr(obj.usuario, 'apellidos', '') or '').strip()
        return ' '.join([p for p in [nombres, apellidos] if p]) or None

    def get_usuario_prestador_rut(self, obj):
        return getattr(obj.usuario, 'rut', None) if obj.usuario else None

    def get_usuario_receptor_nombre(self, obj):
        usuario = getattr(obj.prestamo, 'id_usuario', None) if obj.prestamo else None
        if not usuario:
            return None
        nombres = (getattr(usuario, 'nombres', '') or '').strip()
        apellidos = (getattr(usuario, 'apellidos', '') or '').strip()
        return ' '.join([p for p in [nombres, apellidos] if p]) or None

    def get_usuario_receptor_rut(self, obj):
        usuario = getattr(obj.prestamo, 'id_usuario', None) if obj.prestamo else None
        return getattr(usuario, 'rut', None) if usuario else None

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
            'usuario_prestador_id',
            'usuario_prestador_nombre',
            'usuario_prestador_rut',
            'usuario_receptor_id',
            'usuario_receptor_nombre',
            'usuario_receptor_rut',
        ]
