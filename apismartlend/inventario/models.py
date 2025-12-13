from django.conf import settings
from django.db import models

# Create your models here.
class categoria_herramienta(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

class tipo_herramienta(models.Model):
    id_tipo_herramienta = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=200)
    stock = models.IntegerField(default=0, editable=False)  # Disponibles menos reservados
    reservado = models.PositiveIntegerField(default=0, editable=False)
    imagen = models.ImageField(upload_to='tipos_herramienta/', null=True, blank=True)
    id_categoria = models.ForeignKey(categoria_herramienta, on_delete=models.CASCADE)

    def recalcular_stock(self):
        disponibles = self.herramienta_individual_set.filter(disponible=True).count()
        nuevo_stock = max(disponibles - self.reservado, 0)
        tipo_herramienta.objects.filter(pk=self.pk).update(stock=nuevo_stock)
        self.stock = nuevo_stock

    def ajustar_reserva(self, delta_cantidad):
        nueva_reserva = self.reservado + delta_cantidad
        if nueva_reserva < 0:
            raise ValueError('Reservado no puede ser negativo')
        disponibles = self.herramienta_individual_set.filter(disponible=True).count()
        nuevo_stock = max(disponibles - nueva_reserva, 0)
        tipo_herramienta.objects.filter(pk=self.pk).update(reservado=nueva_reserva, stock=nuevo_stock)
        self.reservado = nueva_reserva
        self.stock = nuevo_stock

class herramienta_individual(models.Model):
    class EstadoHerramienta(models.TextChoices):
        NUEVO = 'Nuevo', 'Nuevo'
        EXCELENTE = 'Excelente', 'Excelente'
        BUENO = 'Bueno', 'Bueno'
        REGULAR = 'Regular', 'Regular'
        DEFECTUOSO = 'Defectuoso', 'Defectuoso'
        DANADO = 'Dañado', 'Dañado'

    id_herramienta = models.AutoField(primary_key=True)
    codigo_barras = models.CharField(max_length=50, unique=True)
    imagen = models.ImageField(upload_to='herramientas/', null=True, blank=True)
    estado_herramienta = models.CharField(
        max_length=50,
        choices=EstadoHerramienta.choices,
    )
    disponible = models.BooleanField(default=True) # Indica si la herramienta está disponible para préstamo o reserva
    fecha_adquisicion = models.DateTimeField()
    id_tipo_herramienta = models.ForeignKey(tipo_herramienta, on_delete=models.CASCADE)

    # Esto es para recalcular el stock automáticamente al guardar o borrar una herramienta individual
    def save(self, *args, **kwargs):
        old_tipo_id = None
        if self.pk:
            old_tipo_id = herramienta_individual.objects.filter(
                pk=self.pk,
            ).values_list('id_tipo_herramienta_id', flat=True).first()
        ### Super.save sirve para llamar al metodo save original de Django
        super().save(*args, **kwargs)
        ### Estoy llamando a la funcion de recalc stock para el tipo actual
        self._recalc_stock(self.id_tipo_herramienta_id)
        if old_tipo_id and old_tipo_id != self.id_tipo_herramienta_id:
            self._recalc_stock(old_tipo_id)

    def delete(self, *args, **kwargs):
        tipo_id = self.id_tipo_herramienta_id
        super().delete(*args, **kwargs)
        self._recalc_stock(tipo_id)

    @staticmethod
    def _recalc_stock(tipo_id):
        if tipo_id is None:
            return
        tipo = tipo_herramienta.objects.filter(pk=tipo_id).first()
        if tipo:
            tipo.recalcular_stock()


class historial_herramienta(models.Model):
    id_historial = models.AutoField(primary_key=True)
    herramienta = models.ForeignKey(herramienta_individual, on_delete=models.CASCADE, related_name='historial')
    estado_herramienta = models.CharField(
        max_length=50,
        choices=herramienta_individual.EstadoHerramienta.choices,
    )
    registrada_en = models.DateTimeField(auto_now_add=True)
    prestamo = models.ForeignKey('operaciones.prestamo', on_delete=models.CASCADE, related_name='historial_herramientas')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.herramienta.codigo_barras} - {self.estado_herramienta} - {self.registrada_en:%Y-%m-%d %H:%M}"
