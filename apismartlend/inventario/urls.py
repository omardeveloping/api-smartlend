from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaHerramientaViewSet,
    TipoHerramientaViewSet,
    HerramientaIndividualViewSet,
    HistorialHerramientaViewSet,
)

router = DefaultRouter()
router.register(r'tipos-herramienta', TipoHerramientaViewSet, basename='tipo-herramienta')
router.register(r'categorias-herramienta', CategoriaHerramientaViewSet, basename='categoria-herramienta')
router.register(r'herramientas', HerramientaIndividualViewSet, basename='herramienta')
router.register(r'historial-herramientas', HistorialHerramientaViewSet, basename='historial-herramienta')

urlpatterns = [
    path('api/', include(router.urls)),
]
