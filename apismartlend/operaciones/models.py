import random
import string

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
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

class prestamoHerramienta(models.Model):
    id_prestamo = models.ForeignKey('prestamo', on_delete=models.CASCADE, related_name='detalle_herramientas')
    id_herramienta_individual = models.ForeignKey('inventario.herramienta_individual', on_delete=models.CASCADE, related_name='prestamos')

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
    herramientas = models.ManyToManyField('inventario.herramienta_individual', through=prestamoHerramienta, related_name='prestamos_asociados')
    id_tipo_herramienta = models.ForeignKey('inventario.tipo_herramienta', on_delete=models.CASCADE)
    codigo = models.CharField(max_length=20, null=True, blank=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.codigo and self.id_usuario_id:
            letras = ''.join(random.choices(string.ascii_uppercase, k=2))
            iniciales = f"{(self.id_usuario.nombres or '')[:1]}{(self.id_usuario.apellidos or '')[:1]}".upper()
            ahora = timezone.now()
            fecha_min = f"{ahora.day:02d}{ahora.month:02d}{ahora.minute:02d}"
            self.codigo = f"{letras}-{iniciales}{fecha_min}"
        super().save(*args, **kwargs)

        # Enviar correo al crear el préstamo con el código asignado
        if is_new and self.id_usuario and getattr(self.id_usuario, 'correo', None):
            try:
                cuerpo = (
                    f"Hola {self.id_usuario.nombres} {self.id_usuario.apellidos}!\n"
                    "Este es el código de tu préstamo en Smartlend:\n\n"
                    f" {self.codigo}\n\n"
                    "Dirígete al pañol y presenta este código para recibir tus insumos."
                )
                send_mail(
                    subject="Tu código de préstamo en Smartlend",
                    message=cuerpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[self.id_usuario.correo],
                    fail_silently=True,
                )
            except Exception:
                # No bloquear el guardado por error de correo
                pass

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
