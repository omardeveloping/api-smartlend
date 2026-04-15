import json
import secrets
from datetime import timedelta

import numpy as np
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.decorators import action
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from operaciones.models import prestamo
from operaciones.serializers import PrestamoSerializer

from .face_utils import FaceProcessor
from .models import DirectorCarrera, Usuario, carrera, rol_usuarios
from .permissions import (
    ROLE_BODEGUERO,
    EsBodeguero,
    EsBodegueroOSelf,
    user_role_code,
)
from .serializers import (
    CarreraSerializer,
    ConfirmarRecuperacionPasswordSerializer,
    DirectorCarreraSerializer,
    LoginBodegueroSerializer,
    RecuperarPasswordSerializer,
    RolUsuarioSerializer,
    UsuarioSerializer,
)


processor = FaceProcessor()
RECOVERY_CODE_TTL_MINUTES = 30


def _is_128d(embedding):
    arr = np.asarray(embedding)
    return arr.shape == (128,)


def _director_email(usuario):
    if not usuario.id_carrera_id:
        return None
    try:
        return usuario.id_carrera.director.correo  # type: ignore[attr-defined]
    except DirectorCarrera.DoesNotExist:
        return None


def _token_para_usuario(usuario):
    token, _ = Token.objects.get_or_create(user=usuario)
    return token.key


def _recovery_success_response():
    return Response(
        {'success': True, 'message': 'Si el correo existe, se envió un código de recuperación.'},
        status=status.HTTP_200_OK,
    )


def _recovery_invalid_response():
    return Response(
        {'error': 'Código inválido o expirado.'},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _bodeguero_recovery_user(correo):
    user = Usuario.objects.select_related('id_rol').filter(
        correo__iexact=correo,
        is_active=True,
    ).first()
    if user is None or user_role_code(user) != ROLE_BODEGUERO:
        return None
    return user


class RolUsuarioViewSet(viewsets.ModelViewSet):
    queryset = rol_usuarios.objects.all()
    serializer_class = RolUsuarioSerializer
    permission_classes = [EsBodeguero]


class DirectorCarreraViewSet(viewsets.ModelViewSet):
    queryset = DirectorCarrera.objects.select_related('carrera').all()
    serializer_class = DirectorCarreraSerializer
    permission_classes = [EsBodeguero]


class CarreraViewSet(viewsets.ModelViewSet):
    queryset = carrera.objects.all()
    serializer_class = CarreraSerializer
    permission_classes = [EsBodeguero]


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.select_related('id_carrera', 'id_rol').all()
    serializer_class = UsuarioSerializer
    permission_classes = [EsBodegueroOSelf]

    def get_permissions(self):
        if self.action in {'list', 'create', 'destroy'}:
            return [EsBodeguero()]
        return super().get_permissions()

    def _serialize_prestamos(self, queryset):
        prestamos_qs = queryset.prefetch_related(
            'herramientas',
            'herramientas__id_tipo_herramienta',
            'tipos_prestamo__tipo_herramienta',
        ).order_by('-fecha_prestamo')
        return PrestamoSerializer(prestamos_qs, many=True, context=self.get_serializer_context()).data

    @action(detail=True, methods=['get'], url_path='historial-prestamos')
    def historial_prestamos(self, request, pk=None):
        usuario = self.get_object()
        historial = prestamo.objects.filter(
            id_usuario=usuario,
            estado_prestamo=prestamo.EstadoPrestamo.FINALIZADO,
        )
        data = self._serialize_prestamos(historial)
        return Response(
            {
                'usuario': self.get_serializer(usuario).data,
                'total': len(data),
                'prestamos': data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'], url_path='prestamos-activos')
    def prestamos_activos(self, request, pk=None):
        usuario = self.get_object()
        activos = prestamo.objects.filter(
            id_usuario=usuario,
            estado_prestamo__in=[
                prestamo.EstadoPrestamo.PENDIENTE,
                prestamo.EstadoPrestamo.ENTREGADO,
                prestamo.EstadoPrestamo.VENCIDO,
            ],
        )
        data = self._serialize_prestamos(activos)
        return Response(
            {
                'usuario': self.get_serializer(usuario).data,
                'total': len(data),
                'prestamos': data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'], url_path='estado-bloqueo')
    def estado_bloqueo(self, request, pk=None):
        usuario = self.get_object()
        activos_vencidos = prestamo.objects.filter(
            id_usuario=usuario,
            fecha_devolucion_real__isnull=True,
            estado_prestamo=prestamo.EstadoPrestamo.VENCIDO,
        ).count()
        return Response(
            {
                'usuario_id': usuario.id,
                'correo': usuario.correo,
                'esta_baneado': usuario.esta_baneado,
                'baneado_en': usuario.baneado_en,
                'aviso_ban_enviado': usuario.aviso_ban_enviado,
                'prestamos_vencidos_activos': activos_vencidos,
                'director_correo': _director_email(usuario),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'], url_path='dashboard-bodeguero')
    def dashboard_bodeguero(self, request, pk=None):
        usuario = self.get_object()
        historial = prestamo.objects.filter(
            id_usuario=usuario,
            estado_prestamo=prestamo.EstadoPrestamo.FINALIZADO,
        )
        activos = prestamo.objects.filter(
            id_usuario=usuario,
            estado_prestamo__in=[
                prestamo.EstadoPrestamo.PENDIENTE,
                prestamo.EstadoPrestamo.ENTREGADO,
                prestamo.EstadoPrestamo.VENCIDO,
            ],
        )
        historial_data = self._serialize_prestamos(historial)
        activos_data = self._serialize_prestamos(activos)
        return Response(
            {
                'usuario': self.get_serializer(usuario).data,
                'estado_bloqueo': {
                    'esta_baneado': usuario.esta_baneado,
                    'baneado_en': usuario.baneado_en,
                    'aviso_ban_enviado': usuario.aviso_ban_enviado,
                    'director_correo': _director_email(usuario),
                },
                'historial_finalizados': {
                    'total': len(historial_data),
                    'prestamos': historial_data,
                },
                'prestamos_activos': {
                    'total': len(activos_data),
                    'prestamos': activos_data,
                },
            },
            status=status.HTTP_200_OK,
        )


class LoginBodegueroView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginBodegueroSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        correo = serializer.validated_data['correo']
        password = serializer.validated_data['password']

        user = authenticate(request, username=correo, password=password)
        if user is None:
            return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
        if user.esta_baneado:
            return Response(
                {
                    'error': 'BANNED: préstamo vencido por más de 20 días. Se notificó al director de carrera.',
                    'director_correo': _director_email(user),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if user_role_code(user) != ROLE_BODEGUERO:
            return Response({'error': 'Rol no autorizado para este login'}, status=status.HTTP_403_FORBIDDEN)

        login(request, user)
        token = _token_para_usuario(user)

        return Response(
            {
                'success': True,
                'usuario_id': user.id,
                'correo': user.correo,
                'nombres': user.nombres,
                'apellidos': user.apellidos,
                'rol': user.id_rol.nombre if user.id_rol else None,
                'token': token,
                'token_type': 'Token',
            },
            status=status.HTTP_200_OK,
        )


class RecuperarPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = RecuperarPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        correo = serializer.validated_data['correo']
        user = _bodeguero_recovery_user(correo)

        if user:
            codigo = f"{secrets.randbelow(1000000):06d}"
            user.codigo_recuperacion_hash = make_password(codigo)
            user.codigo_recuperacion_expira = timezone.now() + timedelta(minutes=RECOVERY_CODE_TTL_MINUTES)
            user.save(update_fields=['codigo_recuperacion_hash', 'codigo_recuperacion_expira'])

            cuerpo = (
                f"Hola {user.nombres},\n\n"
                f"Tu código de recuperación de contraseña es: {codigo}\n"
                f"Este código vence en {RECOVERY_CODE_TTL_MINUTES} minutos.\n\n"
                "Si no solicitaste este cambio, ignora este correo."
            )

            try:
                send_mail(
                    subject='Recuperación de contraseña Smartlend',
                    message=cuerpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.correo],
                    fail_silently=False,
                )
            except Exception:
                # Si el correo falla, invalida el código para no dejar una recuperación colgada.
                user.codigo_recuperacion_hash = None
                user.codigo_recuperacion_expira = None
                user.save(update_fields=['codigo_recuperacion_hash', 'codigo_recuperacion_expira'])

        return _recovery_success_response()


class ConfirmarRecuperacionPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ConfirmarRecuperacionPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        correo = serializer.validated_data['correo']
        codigo = serializer.validated_data['codigo']
        nueva_password = serializer.validated_data['nueva_password']

        user = _bodeguero_recovery_user(correo)
        if (
            user is None
            or not user.codigo_recuperacion_hash
            or not user.codigo_recuperacion_expira
        ):
            return _recovery_invalid_response()

        if timezone.now() > user.codigo_recuperacion_expira:
            user.codigo_recuperacion_hash = None
            user.codigo_recuperacion_expira = None
            user.save(update_fields=['codigo_recuperacion_hash', 'codigo_recuperacion_expira'])
            return _recovery_invalid_response()

        if not check_password(codigo, user.codigo_recuperacion_hash):
            return _recovery_invalid_response()

        user.set_password(nueva_password)
        user.codigo_recuperacion_hash = None
        user.codigo_recuperacion_expira = None
        user.save(update_fields=['password', 'codigo_recuperacion_hash', 'codigo_recuperacion_expira'])
        Token.objects.filter(user=user).delete()

        return Response(
            {'success': True, 'message': 'Contraseña actualizada correctamente.'},
            status=status.HTTP_200_OK,
        )


class LoginUsuarioView(generics.GenericAPIView):
    """
    Login genérico para pruebas (cualquier rol). Solo requiere correo y password.
    """
    permission_classes = [AllowAny]
    serializer_class = LoginBodegueroSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        correo = serializer.validated_data['correo']
        password = serializer.validated_data['password']

        user = authenticate(request, username=correo, password=password)
        if user is None:
            return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
        if user.esta_baneado:
            return Response(
                {
                    'error': 'BANNED: préstamo vencido por más de 20 días. Se notificó al director de carrera.',
                    'director_correo': _director_email(user),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        login(request, user)
        token = _token_para_usuario(user)

        return Response(
            {
                'success': True,
                'usuario_id': user.id,
                'correo': user.correo,
                'nombres': user.nombres,
                'apellidos': user.apellidos,
                'rol': user.id_rol.nombre if user.id_rol else None,
                'token': token,
                'token_type': 'Token',
            },
            status=status.HTTP_200_OK,
        )

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def register_face(request):
    if request.method == 'GET':
        return Response(
            {'detail': 'Envía la imagen en el campo "image" junto con rut, nombres, apellidos, correo, rol y carrera (opcional).'},
            status=status.HTTP_200_OK,
        )

    if 'image' not in request.FILES:
        return Response({'error': 'Falta la imagen'}, status=status.HTTP_400_BAD_REQUEST)

    image_file = request.FILES['image']
    print(f"[register_face] recibido archivo {image_file.name}, size={image_file.size}")

    embedding = processor.extract_embedding(image_file)
    if isinstance(embedding, str) and embedding == 'invalid':
        print("[register_face] archivo de imagen inválido")
        return Response({'error': 'Archivo de imagen inválido'}, status=status.HTTP_400_BAD_REQUEST)
    if embedding is None:
        print("[register_face] no se detectó rostro")
        return Response({'error': 'No se detectó rostro válido'}, status=status.HTTP_400_BAD_REQUEST)
    if not _is_128d(embedding):
        print(f"[register_face] embedding dimensión inválida: {np.asarray(embedding).shape}")
        return Response({'error': 'Embedding con dimensión inválida'}, status=status.HTTP_400_BAD_REQUEST)

    encrypted = processor.encrypt_embedding(embedding)

    rut = request.data.get('rut')
    nombres = request.data.get('nombres')
    apellidos = request.data.get('apellidos')
    correo = request.data.get('correo')
    rol_nombre = request.data.get('rol')
    carrera_nombre = request.data.get('carrera')

    if not all([rut, nombres, apellidos, correo, rol_nombre]):
        return Response({'error': 'Campos obligatorios faltantes'}, status=status.HTTP_400_BAD_REQUEST)

    rol = get_object_or_404(
        rol_usuarios,
        Q(codigo__iexact=rol_nombre) | Q(nombre__iexact=rol_nombre),
    )
    carrera_obj = (
        carrera.objects.filter(nombre__iexact=carrera_nombre).first()
        if carrera_nombre else None
    )

    usuario, created = Usuario.objects.update_or_create(
        rut=rut,
        defaults={
            'nombres': nombres,
            'apellidos': apellidos,
            'correo': correo,
            'embedding': encrypted,
            'id_rol': rol,
            'id_carrera': carrera_obj,
        },
    )

    return Response(
        {'success': True, 'usuario_id': usuario.id, 'created': created},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


def _parse_embedding(raw_embedding):
    if raw_embedding is None:
        raise ValueError('Falta el embedding')

    payload = raw_embedding
    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            raise ValueError('Embedding vacío')
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            try:
                payload = [float(value) for value in payload.split(',') if value.strip()]
            except ValueError as exc:
                raise ValueError('Embedding debe ser una lista de números válidos') from exc

    if not isinstance(payload, (list, tuple)):
        raise ValueError('Embedding debe ser una lista de números')
    if not payload:
        raise ValueError('Embedding vacío')

    try:
        return np.asarray([float(value) for value in payload], dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise ValueError('Embedding debe contener solo números') from exc


def _embedding_from_image(image_file):
    embedding = processor.extract_embedding(image_file)
    if isinstance(embedding, str) and embedding == 'invalid':
        raise ValueError('Archivo de imagen inválido')
    if embedding is None:
        raise ValueError('No se detectó rostro válido')
    return embedding


@api_view(['POST'])
@permission_classes([AllowAny])
def login_face(request):
    if 'image' in request.FILES:
        try:
            incoming_embedding = _embedding_from_image(request.FILES['image'])
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    else:
        try:
            incoming_embedding = _parse_embedding(request.data.get('embedding'))
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if not _is_128d(incoming_embedding):
        return Response({'error': 'Embedding con dimensión inválida'}, status=status.HTTP_400_BAD_REQUEST)

    usuarios = Usuario.objects.select_related('id_rol').exclude(embedding__isnull=True).exclude(embedding__exact='')
    for usuario in usuarios.iterator():
        stored_embedding = processor.decrypt_embedding(usuario.embedding)
        if not _is_128d(stored_embedding):
            continue
        is_match, _ = processor.match_embeddings(incoming_embedding, stored_embedding)
        if is_match:
            if usuario.esta_baneado:
                return Response(
                    {
                        'error': 'BANNED: préstamo vencido por más de 20 días. Se notificó al director de carrera.',
                        'director_correo': _director_email(usuario),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            login(request, usuario, backend='django.contrib.auth.backends.ModelBackend')
            token = _token_para_usuario(usuario)
            return Response(
                {
                    'success': True,
                    'existe_embedding': True,
                    'usuario_id': usuario.id,
                    'correo': usuario.correo,
                    'nombres': usuario.nombres,
                    'apellidos': usuario.apellidos,
                    'rol': usuario.id_rol.nombre if usuario.id_rol else None,
                    'token': token,
                    'token_type': 'Token',
                },
                status=status.HTTP_200_OK,
            )

    return Response({'existe_embedding': False}, status=status.HTTP_200_OK)
