from rest_framework import serializers

from .models import (
    prestamo,
    reserva,
)

class ReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = reserva
        fields = '__all__'


class PrestamoSerializer(serializers.ModelSerializer):
    class Meta:
        model = prestamo
        fields = '__all__'
