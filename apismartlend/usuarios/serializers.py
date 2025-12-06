from rest_framework import serializers

from .models import DirectorCarrera, Usuario, carrera as CarreraModel, rol_usuarios


class LoginBodegueroSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})


class CarreraSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarreraModel
        fields = '__all__'


class DirectorCarreraSerializer(serializers.ModelSerializer):
    carrera = CarreraSerializer(read_only=True)
    carrera_id = serializers.PrimaryKeyRelatedField(
        source='carrera',
        queryset=CarreraModel.objects.all(),
        write_only=True,
    )

    class Meta:
        model = DirectorCarrera
        fields = ['id_director', 'nombre', 'correo', 'carrera', 'carrera_id']
        read_only_fields = ('id_director',)


class RolUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = rol_usuarios
        fields = '__all__'


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    carrera = CarreraSerializer(source='id_carrera', read_only=True)
    embedding = serializers.CharField(read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id',
            'password',
            'rut',
            'embedding',
            'nombres',
            'apellidos',
            'id_carrera',
            'carrera',
            'correo',
            'id_rol',
            'esta_baneado',
            'baneado_en',
            'aviso_ban_enviado',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'date_joined',
        ]
        read_only_fields = (
            'id',
            'embedding',
            'baneado_en',
            'aviso_ban_enviado',
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
