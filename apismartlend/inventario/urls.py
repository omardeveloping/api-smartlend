from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaHerramientaViewSet,
    EstadoHerramientaViewSet,
    HerramientaViewSet,
)

router = DefaultRouter()
router.register(r'estados-herramienta', EstadoHerramientaViewSet, basename='estado-herramienta')
router.register(r'categorias-herramienta', CategoriaHerramientaViewSet, basename='categoria-herramienta')
router.register(r'herramientas', HerramientaViewSet, basename='herramienta')

urlpatterns = [
    path('api/', include(router.urls)),
]
