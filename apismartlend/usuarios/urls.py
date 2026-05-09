from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CarreraViewSet,
    ConfirmarRecuperacionPasswordView,
    DirectorCarreraViewSet,
    EnviarAsistenciaTecnicaView,
    LoginBodegueroView,
    LoginUsuarioView,
    RecuperarPasswordView,
    RegistroInstitucionalView,
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
    path(
        'api/soporte/enviar-asistencia/',
        EnviarAsistenciaTecnicaView.as_view(),
        name='enviar-asistencia-tecnica',
    ),
    path(
        'api/registro-institucional/',
        RegistroInstitucionalView.as_view(),
        name='registro-institucional',
    ),
    path('auth/register-face/', register_face, name='register-face'),
    path('auth/login/', login_face, name='login-face'),
    path('auth/login-bodeguero/', LoginBodegueroView.as_view(), name='login-bodeguero'),
    path('auth/login-usuario/', LoginUsuarioView.as_view(), name='login-usuario'),
    path('auth/recuperar-password/', RecuperarPasswordView.as_view(), name='recuperar-password'),
    path(
        'auth/confirmar-recuperacion-password/',
        ConfirmarRecuperacionPasswordView.as_view(),
        name='confirmar-recuperacion-password',
    ),
]
