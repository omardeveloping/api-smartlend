from django.conf import settings
from django.db import models
# ### 1. IMPORTANTE: Importamos el modelo de inventario para poder usar sus opciones (Estados de herramienta)
from inventario.models import herramienta_individual

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
    # ### 2. NUEVO: Definimos las opciones permitidas para un Préstamo
    class EstadoPrestamo(models.TextChoices):
        ACTIVO = 'Activo', 'Activo'
        FINALIZADO = 'Finalizado', 'Finalizado'
        VENCIDO = 'Vencido', 'Vencido'
        CANCELADO = 'Cancelado', 'Cancelado'

    id_prestamo = models.AutoField(primary_key=True)
    fecha_prestamo = models.DateTimeField()
    fecha_devolucion_esperada = models.DateTimeField()
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)
    
    # ### 3. CAMBIO: Enlazamos este campo con las opciones de arriba
    estado_prestamo = models.CharField(
        max_length=50,
        choices=EstadoPrestamo.choices,
        default=EstadoPrestamo.ACTIVO
    )

    # ### 4. CAMBIO: Enlazamos este campo con las opciones que ya existen en "herramienta_individual"
    estado_devolucion = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        choices=herramienta_individual.EstadoHerramienta.choices
    )

    observaciones = models.CharField(max_length=200, null=True, blank=True)
    id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    id_herramienta_individual = models.ForeignKey('inventario.herramienta_individual', on_delete=models.CASCADE)
    id_tipo_herramienta = models.ForeignKey('inventario.tipo_herramienta', on_delete=models.CASCADE)

class alerta(models.Model):
    id_alerta = models.AutoField(primary_key=True)
    prestamo = models.OneToOneField(prestamo, on_delete=models.CASCADE, related_name='alerta')
    mensaje = models.CharField(max_length=200, default='Prestamo vencido')
    criticidad = models.CharField(max_length=20, null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta = models.BooleanField(default=False)
    resuelta_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Alerta prestamo {self.prestamo_id}'

class test(models.Model):
    id_test = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50 )
