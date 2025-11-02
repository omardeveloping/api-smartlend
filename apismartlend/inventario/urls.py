from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaHerramientaViewSet,
    TipoHerramientaViewSet,
    HerramientaIndividualViewSet,
)

router = DefaultRouter()
router.register(r'tipos-herramienta', TipoHerramientaViewSet, basename='tipo-herramienta')
router.register(r'categorias-herramienta', CategoriaHerramientaViewSet, basename='categoria-herramienta')
router.register(r'herramientas', HerramientaIndividualViewSet, basename='herramienta')

urlpatterns = [
    path('api/', include(router.urls)),
]
