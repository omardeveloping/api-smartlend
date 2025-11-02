from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PrestamoViewSet,
    ReservaViewSet,
)

router = DefaultRouter()
router.register(r'reservas', ReservaViewSet, basename='reserva')
router.register(r'prestamos', PrestamoViewSet, basename='prestamo')

urlpatterns = [
    path('api/', include(router.urls)),
]
