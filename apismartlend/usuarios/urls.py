from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RolUsuarioViewSet, UsuarioViewSet, login_face, register_face

router = DefaultRouter()
router.register(r'roles', RolUsuarioViewSet, basename='rol-usuario')
router.register(r'usuarios', UsuarioViewSet, basename='usuario')

urlpatterns = [
    path('api/', include(router.urls)),
    path('auth/register-face/', register_face, name='register-face'),
    path('auth/login/', login_face, name='login-face'),
]
