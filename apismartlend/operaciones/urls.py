from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlertasViewSet, PrestamoViewSet

router = DefaultRouter()
router.register(r'prestamos', PrestamoViewSet, basename='prestamo')
router.register(r'alertas', AlertasViewSet, basename='alerta')

urlpatterns = [
    path('api/', include(router.urls)),
]
