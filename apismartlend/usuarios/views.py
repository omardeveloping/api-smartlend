from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .face_utils import FaceProcessor
from .models import Usuario, carrera, rol_usuarios
from .serializers import RolUsuarioSerializer, UsuarioSerializer

processor = FaceProcessor()


class RolUsuarioViewSet(viewsets.ModelViewSet):
    queryset = rol_usuarios.objects.all()
    serializer_class = RolUsuarioSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

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
