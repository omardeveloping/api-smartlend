from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlertasViewSet, PrestamoViewSet, ReportesViewSet, TurneroViewSet

router = DefaultRouter()
router.register(r'prestamos', PrestamoViewSet, basename='prestamo')
router.register(r'alertas', AlertasViewSet, basename='alerta')
router.register(r'reportes', ReportesViewSet, basename='reporte')
router.register(r'turnero', TurneroViewSet, basename='turnero')

urlpatterns = [
    path('api/', include(router.urls)),
]
