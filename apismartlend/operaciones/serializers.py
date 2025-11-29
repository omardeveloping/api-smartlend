from django.utils import timezone
from rest_framework import serializers

from .models import (
    alerta,
    prestamo,
    reserva,
)


class ReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = reserva
        fields = '__all__'


class PrestamoSerializer(serializers.ModelSerializer):
    esta_vencido = serializers.SerializerMethodField()

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
            'id_usuario',
            'id_herramienta_individual',
            'id_tipo_herramienta',
            'esta_vencido',
        ]

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
            'creada_en',
            'resuelta',
            'resuelta_en',
        ]
