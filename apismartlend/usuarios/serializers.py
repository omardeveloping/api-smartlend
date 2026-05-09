from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.db.models import Q
from rest_framework import serializers

from .models import DirectorCarrera, Usuario, carrera as CarreraModel, rol_usuarios
from .permissions import ROLE_DOCENTE, ROLE_ESTUDIANTE, is_bodeguero


class LoginBodegueroSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})


class AsistenciaTecnicaSerializer(serializers.Serializer):
    rol = serializers.CharField(max_length=50)
    ventana = serializers.CharField(max_length=120)
    descripcion = serializers.CharField()
    destinatario = serializers.EmailField(required=False, allow_blank=True)


class RecuperarPasswordSerializer(serializers.Serializer):
    correo = serializers.EmailField()


class ConfirmarRecuperacionPasswordSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    codigo = serializers.CharField(max_length=6)
    nueva_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    def validate_nueva_password(self, value):
        validate_password(value)
        return value


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
        request = self.context.get('request')
        if request is not None and request.user.is_authenticated and not is_bodeguero(request.user):
            for restricted_field in (
                'id_rol',
                'esta_baneado',
                'is_active',
                'is_staff',
                'is_superuser',
                'aviso_ban_enviado',
                'baneado_en',
            ):
                validated_data.pop(restricted_field, None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        return user


class RegistroInstitucionalSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    codigo_acceso = serializers.CharField(
        write_only=True,
        required=True,
        trim_whitespace=True,
        error_messages={
            'blank': 'El campo codigo_acceso es obligatorio para este perfil.',
            'required': 'El campo codigo_acceso es obligatorio para este perfil.',
        },
    )
    carrera = CarreraSerializer(source='id_carrera', read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id',
            'password',
            'rut',
            'nombres',
            'apellidos',
            'id_carrera',
            'carrera',
            'correo',
            'codigo_acceso',
        ]
        read_only_fields = ('id', 'carrera')

    def _codigo_a_rol(self, codigo_acceso):
        codigos = {
            str(settings.SMARTLEND_CODIGO_ACCESO_ESTUDIANTE).strip(): ROLE_ESTUDIANTE,
            str(settings.SMARTLEND_CODIGO_ACCESO_DOCENTE).strip(): ROLE_DOCENTE,
        }
        return codigos.get(str(codigo_acceso).strip())

    def _obtener_rol(self, codigo_rol):
        alias_por_rol = {
            ROLE_ESTUDIANTE: ('ESTUDIANTE', 'ALUMNO'),
            ROLE_DOCENTE: ('DOCENTE', 'PROFESOR'),
        }
        query = Q()
        for alias in alias_por_rol.get(codigo_rol, (codigo_rol,)):
            query |= Q(codigo__iexact=alias) | Q(nombre__iexact=alias)

        rol = rol_usuarios.objects.filter(query).first()
        if rol is None:
            raise serializers.ValidationError(
                {'error': f'No existe un rol configurado para {codigo_rol}.'}
            )
        return rol

    def validate(self, attrs):
        codigo_acceso = attrs.pop('codigo_acceso', None)
        codigo_rol = self._codigo_a_rol(codigo_acceso)
        if codigo_rol is None:
            raise serializers.ValidationError({'error': 'Código de acceso inválido o expirado.'})

        if codigo_rol == ROLE_ESTUDIANTE and attrs.get('id_carrera') is None:
            raise serializers.ValidationError(
                {'error': 'El campo id_carrera es obligatorio para este perfil.'}
            )

        attrs['_codigo_rol'] = codigo_rol
        return attrs

    def create(self, validated_data):
        codigo_rol = validated_data.pop('_codigo_rol')
        password = validated_data.pop('password')
        rol = self._obtener_rol(codigo_rol)

        user = Usuario.objects.create(id_rol=rol, **validated_data)
        user.set_password(password)
        user.save(update_fields=['password'])
        return user
