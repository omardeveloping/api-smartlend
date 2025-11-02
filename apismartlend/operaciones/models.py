from django.conf import settings
from django.db import models

# Create your models here.
class reserva(models.Model):
    id_reserva = models.AutoField(primary_key=True)
    fecha_reserva = models.DateTimeField()
    fecha_inicio_reserva = models.DateTimeField()
    fecha_fin_reserva = models.DateTimeField()
    estado_reserva = models.CharField(max_length=50)
    id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    id_tipo_herramienta = models.ForeignKey('inventario.tipo_herramienta', on_delete=models.CASCADE)

class prestamo(models.Model):
    id_prestamo = models.AutoField(primary_key=True)
    fecha_prestamo = models.DateTimeField()
    fecha_devolucion_esperada = models.DateTimeField()
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)
    estado_prestamo = models.CharField(max_length=50)
    estado_devolucion = models.CharField(max_length=50, null=True, blank=True)
    observaciones = models.CharField(max_length=200, null=True, blank=True)
    id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    id_herramienta_individual = models.ForeignKey('inventario.herramienta_individual', on_delete=models.CASCADE)
    id_tipo_herramienta = models.ForeignKey('inventario.tipo_herramienta', on_delete=models.CASCADE)

class test(models.Model):
    id_test = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50 )