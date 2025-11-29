import json

import numpy as np
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import generics

from .face_utils import FaceProcessor
from .models import Usuario, carrera, rol_usuarios
from .serializers import CarreraSerializer, LoginBodegueroSerializer, RolUsuarioSerializer, UsuarioSerializer

processor = FaceProcessor()


class RolUsuarioViewSet(viewsets.ModelViewSet):
    queryset = rol_usuarios.objects.all()
    serializer_class = RolUsuarioSerializer


class CarreraViewSet(viewsets.ModelViewSet):
    queryset = carrera.objects.all()
    serializer_class = CarreraSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer


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

        if user.id_rol and user.id_rol.nombre.lower() != 'bodeguero':
            return Response({'error': 'Rol no autorizado para este login'}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                'success': True,
                'usuario_id': user.id,
                'correo': user.correo,
                'nombres': user.nombres,
                'apellidos': user.apellidos,
                'rol': user.id_rol.nombre if user.id_rol else None,
            },
            status=status.HTTP_200_OK,
        )

@api_view(['GET', 'POST'])
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

    encrypted = processor.encrypt_embedding(embedding)

    rut = request.data.get('rut')
    nombres = request.data.get('nombres')
    apellidos = request.data.get('apellidos')
    correo = request.data.get('correo')
    rol_nombre = request.data.get('rol')
    carrera_nombre = request.data.get('carrera')

    if not all([rut, nombres, apellidos, correo, rol_nombre]):
        return Response({'error': 'Campos obligatorios faltantes'}, status=status.HTTP_400_BAD_REQUEST)

    rol = get_object_or_404(rol_usuarios, nombre__iexact=rol_nombre)
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

    usuarios = Usuario.objects.exclude(embedding__isnull=True).exclude(embedding__exact='')
    for usuario in usuarios.iterator():
        stored_embedding = processor.decrypt_embedding(usuario.embedding)
        is_match, _ = processor.match_embeddings(incoming_embedding, stored_embedding)
        if is_match:
            return Response(
                {
                    'existe_embedding': True,
                    'usuario_id': usuario.id,
                    'nombres': usuario.nombres,
                    'apellidos': usuario.apellidos,
                },
                status=status.HTTP_200_OK,
            )

    return Response({'existe_embedding': False}, status=status.HTTP_200_OK)
