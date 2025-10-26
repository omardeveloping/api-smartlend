from rest_framework import viewsets

from .models import Usuario, rol_usuarios
from .serializers import RolUsuarioSerializer, UsuarioSerializer


class RolUsuarioViewSet(viewsets.ModelViewSet):
    queryset = rol_usuarios.objects.all()
    serializer_class = RolUsuarioSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
