from rest_framework import serializers

from .models import Usuario, rol_usuarios


class RolUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = rol_usuarios
        fields = '__all__'


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Usuario
        fields = [
            'id',
            'username',
            'password',
            'rut',
            'embedding',
            'nombres',
            'apellidos',
            'carrera',
            'correo',
            'id_rol',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'date_joined',
        ]
        read_only_fields = (
            'id',
            'is_staff',
            'is_superuser',
            'last_login',
            'date_joined',
        )

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        return user
