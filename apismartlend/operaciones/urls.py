from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EstadoDevolucionViewSet,
    EstadoPrestamoViewSet,
    EstadoReservaViewSet,
    PrestamoViewSet,
    ReservaViewSet,
)

router = DefaultRouter()
router.register(r'estados-reserva', EstadoReservaViewSet, basename='estado-reserva')
router.register(r'estados-prestamo', EstadoPrestamoViewSet, basename='estado-prestamo')
router.register(r'estados-devolucion', EstadoDevolucionViewSet, basename='estado-devolucion')
router.register(r'reservas', ReservaViewSet, basename='reserva')
router.register(r'prestamos', PrestamoViewSet, basename='prestamo')

urlpatterns = [
    path('api/', include(router.urls)),
]
