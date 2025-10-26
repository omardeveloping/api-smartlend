from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RolUsuarioViewSet, UsuarioViewSet

router = DefaultRouter()
router.register(r'roles', RolUsuarioViewSet, basename='rol-usuario')
router.register(r'usuarios', UsuarioViewSet, basename='usuario')

urlpatterns = [
    path('api/', include(router.urls)),
]
