from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CarreraViewSet,
    DirectorCarreraViewSet,
    LoginBodegueroView,
    RolUsuarioViewSet,
    UsuarioViewSet,
    login_face,
    register_face,
)

router = DefaultRouter()
router.register(r'roles', RolUsuarioViewSet, basename='rol-usuario')
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'carreras', CarreraViewSet, basename='carrera')
router.register(r'directores', DirectorCarreraViewSet, basename='director')

urlpatterns = [
    path('api/', include(router.urls)),
    path('auth/register-face/', register_face, name='register-face'),
    path('auth/login/', login_face, name='login-face'),
    path('auth/login-bodeguero/', LoginBodegueroView.as_view(), name='login-bodeguero'),
]
