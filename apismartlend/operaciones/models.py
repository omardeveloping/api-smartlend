from django.conf import settings
from django.db import models

# Create your models here.
class estado_reserva(models.Model):
    id_estado_reserva = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=20)

class estado_prestamo(models.Model):
    id_estado_prestamo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=20)

class estado_devolucion(models.Model):
    id_estado_devolucion = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=20)

class reserva(models.Model):
    id_autenticacion = models.AutoField(primary_key=True)
    fecha_reserva = models.DateTimeField()
    fecha_inicio_reserva = models.DateTimeField()
    fecha_fin_reserva = models.DateTimeField()
    fecha_devolucion_esperada = models.DateTimeField()
    id_estado_reserva = models.ForeignKey(estado_reserva, on_delete=models.CASCADE)
    id_herramienta = models.ForeignKey('inventario.herramienta', on_delete=models.CASCADE)
    id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

class prestamo(models.Model):
    id_prestamo = models.AutoField(primary_key=True)
    fecha_prestamo = models.DateTimeField()
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)
    id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    id_herramienta = models.ForeignKey('inventario.herramienta', on_delete=models.CASCADE)
    id_estado_prestamo = models.ForeignKey(estado_prestamo, on_delete=models.CASCADE)
    id_estado_devolucion = models.ForeignKey(estado_devolucion, on_delete=models.CASCADE, null=True, blank=True)
