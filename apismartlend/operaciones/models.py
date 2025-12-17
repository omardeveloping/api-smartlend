import random
import string

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
# ### 1. IMPORTANTE: Importamos el modelo de inventario para poder usar sus opciones (Estados de herramienta)
from inventario.models import herramienta_individual

### Todavía no se trabaja con reservas, sólo con préstamos
class reserva(models.Model):
    id_reserva = models.AutoField(primary_key=True)
    fecha_reserva = models.DateTimeField()
    fecha_inicio_reserva = models.DateTimeField()
    fecha_fin_reserva = models.DateTimeField()
    estado_reserva = models.CharField(max_length=50)
    id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    id_tipo_herramienta = models.ForeignKey('inventario.tipo_herramienta', on_delete=models.CASCADE)
    herramientas = models.ManyToManyField(
        'inventario.herramienta_individual',
        blank=True,
        related_name='reservas_asociadas',
    )
    herramientas = models.ManyToManyField('inventario.herramienta_individual', related_name='reservas_asociadas')

class prestamoHerramienta(models.Model):
    id_prestamo = models.ForeignKey('prestamo', on_delete=models.CASCADE, related_name='detalle_herramientas')
    id_herramienta_individual = models.ForeignKey('inventario.herramienta_individual', on_delete=models.CASCADE, related_name='prestamos')


class PrestamoTipoHerramienta(models.Model):
    prestamo = models.ForeignKey('prestamo', on_delete=models.CASCADE, related_name='tipos_prestamo')
    tipo_herramienta = models.ForeignKey('inventario.tipo_herramienta', on_delete=models.CASCADE, related_name='prestamos_por_tipo')
    cantidad = models.PositiveIntegerField(default=1)


class prestamo(models.Model):
    # ### 2. NUEVO: Definimos las opciones permitidas para un Préstamo
    class EstadoPrestamo(models.TextChoices):
        PENDIENTE = 'Pendiente', 'Pendiente'
        EXPIRADO = 'Expirado', 'Expirado'
        ENTREGADO = 'Entregado', 'Entregado'
        FINALIZADO = 'Finalizado', 'Finalizado'
        VENCIDO = 'Vencido', 'Vencido'
        CANCELADO = 'Cancelado', 'Cancelado'

    id_prestamo = models.AutoField(primary_key=True)
    fecha_prestamo = models.DateTimeField()
    fecha_devolucion_esperada = models.DateTimeField()
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)
    
    # ### Queda pendiente por defecto (que es cuando se crea el prestamo pero las herramientas aún no se entregan al usuario)
    estado_prestamo = models.CharField(
        max_length=50,
        choices=EstadoPrestamo.choices,
        default=EstadoPrestamo.PENDIENTE
    )

    # ### Tengo que hacer registros de esto más adelante
    estado_devolucion = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        choices=herramienta_individual.EstadoHerramienta.choices
    )

    observaciones = models.CharField(max_length=200, null=True, blank=True)
    id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ### Este campo debe ser eliminado en el futuro, ya que un préstamo puede tener varias herramientas asociadas
    ### Todavía no porque no me quiero echar la base de datos
    id_herramienta_individual = models.ForeignKey('inventario.herramienta_individual', on_delete=models.CASCADE, null=True, blank=True)

    ### Las herramientas se dejarán de asignar al momento de crear el prestamo
    ### Se asignarán después, al momento de entregar las herramientas al usuario
    ### Las herramientas que se asignen deben cambiar su estado de disponible a no disponible
    herramientas = models.ManyToManyField('inventario.herramienta_individual', through=prestamoHerramienta, related_name='prestamos_asociados', blank=True, null=True)
    tipos_herramienta = models.ManyToManyField('inventario.tipo_herramienta', through=PrestamoTipoHerramienta, related_name='prestamos_tipo_herramienta')
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

    def enviar_correo_codigo(self, tipos_list=None):
        """
        Envía correo con el código del préstamo y detalle de tipos/cantidades.
        tipos_list: opcional, lista de dicts {'tipo': tipo_herramienta, 'cantidad': int}
        """
        if not self.id_usuario or not getattr(self.id_usuario, 'correo', None):
            return

        try:
            if tipos_list is None:
                tipos_lista = list(self.tipos_prestamo.select_related('tipo_herramienta').all())
                detalle_tipos = '\n'.join(
                    f"- {tp.tipo_herramienta.nombre if tp.tipo_herramienta else 'Tipo sin nombre'} x{tp.cantidad}"
                    for tp in tipos_lista
                ) or '- (Sin tipos de herramienta asignados aún)'
            else:
                detalle_tipos = '\n'.join(
                    f"- {entry['tipo'].nombre if entry.get('tipo') else 'Tipo sin nombre'} x{entry.get('cantidad', 0)}"
                    for entry in tipos_list
                ) or '- (Sin tipos de herramienta asignados aún)'

            cuerpo = (
                f"Hola {self.id_usuario.nombres} {self.id_usuario.apellidos}!\n"
                "Este es el código de tu préstamo en Smartlend:\n\n"
                f" {self.codigo}\n\n"
                "Solicitaste las siguientes herramientas:\n"
                f"{detalle_tipos}\n\n"
                "Dirígete al pañol y presenta este código para recibir tus insumos en los próximos 30 minutos.\n"
                "Si no retiras tus herramientas dentro de ese plazo, el préstamo expirará automáticamente."
            )
            send_mail(
                subject="Tu código de préstamo en Smartlend",
                message=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.id_usuario.correo],
                fail_silently=True,
            )
        except Exception:
            # No bloquear por errores de correo
            pass

class alerta(models.Model):
    id_alerta = models.AutoField(primary_key=True)
    prestamo = models.OneToOneField(prestamo, on_delete=models.CASCADE, related_name='alerta')
    mensaje = models.CharField(max_length=200, default='Prestamo vencido')
    criticidad = models.CharField(max_length=20, null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta = models.BooleanField(default=False)
    resuelta_en = models.DateTimeField(null=True, blank=True)
    archivada = models.BooleanField(default=False)

    def __str__(self):
        return f'Alerta prestamo {self.prestamo_id}'

class test(models.Model):
    id_test = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50 )
