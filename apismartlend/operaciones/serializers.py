from django.utils import timezone
from rest_framework import serializers

from inventario.models import herramienta_individual
from inventario.serializers import HerramientaIndividualSerializer

from .models import (
    alerta,
    prestamo,
    reserva,
)


class ReservaSerializer(serializers.ModelSerializer):
    herramientas = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=herramienta_individual.objects.all(),
        required=False,
    )
    herramientas_detalle = HerramientaIndividualSerializer(source='herramientas', many=True, read_only=True)

    class Meta:
        model = reserva
        fields = [
            'id_reserva',
            'fecha_reserva',
            'fecha_inicio_reserva',
            'fecha_fin_reserva',
            'estado_reserva',
            'id_usuario',
            'id_tipo_herramienta',
            'herramientas',
            'herramientas_detalle',
        ]

    def _get_tipo_id(self):
        if self.instance and getattr(self.instance, 'id_tipo_herramienta_id', None):
            return self.instance.id_tipo_herramienta_id
        data = getattr(self, 'initial_data', None)
        if data:
            tipo_val = data.get('id_tipo_herramienta') or data.get('id_tipo_herramienta_id')
            try:
                return int(tipo_val)
            except (TypeError, ValueError):
                return None
        return None

    def validate_herramientas(self, herramientas):
        tipo_id = self._get_tipo_id()
        if herramientas and not tipo_id:
            raise serializers.ValidationError('Debes indicar id_tipo_herramienta antes de asignar herramientas.')
        if tipo_id:
            for herramienta in herramientas:
                if herramienta.id_tipo_herramienta_id != tipo_id:
                    raise serializers.ValidationError('Todas las herramientas deben pertenecer al tipo seleccionado.')
        return herramientas


class PrestamoSerializer(serializers.ModelSerializer):
    esta_vencido = serializers.SerializerMethodField()
    herramientas = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=herramienta_individual.objects.all(),
        required=False,
    )
    herramientas_detalle = HerramientaIndividualSerializer(source='herramientas', many=True, read_only=True)

    class Meta:
        model = prestamo
        fields = [
            'id_prestamo',
            'fecha_prestamo',
            'fecha_devolucion_esperada',
            'fecha_devolucion_real',
            'estado_prestamo',
            'estado_devolucion',
            'observaciones',
            'codigo',
            'id_usuario',
            'id_tipo_herramienta',
            'herramientas',
            'herramientas_detalle',
            'esta_vencido',
        ]

    def _get_tipo_id(self):
        if self.instance and getattr(self.instance, 'id_tipo_herramienta_id', None):
            return self.instance.id_tipo_herramienta_id
        data = getattr(self, 'initial_data', None)
        if data:
            tipo_val = data.get('id_tipo_herramienta') or data.get('id_tipo_herramienta_id')
            try:
                return int(tipo_val)
            except (TypeError, ValueError):
                return None
        return None

    def validate_herramientas(self, herramientas):
        tipo_id = self._get_tipo_id()
        if herramientas and not tipo_id:
            raise serializers.ValidationError('Debes indicar id_tipo_herramienta antes de asignar herramientas.')
        if tipo_id:
            for herramienta in herramientas:
                if herramienta.id_tipo_herramienta_id != tipo_id:
                    raise serializers.ValidationError('Todas las herramientas deben pertenecer al tipo seleccionado.')
        return herramientas

    def get_esta_vencido(self, obj):
        return (
            obj.fecha_devolucion_real is None
            and obj.fecha_devolucion_esperada
            and obj.fecha_devolucion_esperada < timezone.now()
        )


class AlertaSerializer(serializers.ModelSerializer):
    prestamo_detalle = PrestamoSerializer(source='prestamo', read_only=True)

    class Meta:
        model = alerta
        fields = [
            'id_alerta',
            'prestamo',
            'prestamo_detalle',
            'mensaje',
            'criticidad',
            'creada_en',
            'resuelta',
            'resuelta_en',
        ]
