from rest_framework import serializers

from .models import (
    estado_devolucion,
    estado_prestamo,
    estado_reserva,
    prestamo,
    reserva,
)


class EstadoReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = estado_reserva
        fields = '__all__'


class EstadoPrestamoSerializer(serializers.ModelSerializer):
    class Meta:
        model = estado_prestamo
        fields = '__all__'


class EstadoDevolucionSerializer(serializers.ModelSerializer):
    class Meta:
        model = estado_devolucion
        fields = '__all__'


class ReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = reserva
        fields = '__all__'


class PrestamoSerializer(serializers.ModelSerializer):
    class Meta:
        model = prestamo
        fields = '__all__'
