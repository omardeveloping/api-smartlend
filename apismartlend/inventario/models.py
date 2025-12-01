from django.db import models

# Create your models here.
class categoria_herramienta(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

class tipo_herramienta(models.Model):
    id_tipo_herramienta = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=200)
    imagen_url = models.ImageField(upload_to='tipos_herramienta/', null=True, blank=True)
    id_categoria = models.ForeignKey(categoria_herramienta, on_delete=models.CASCADE)


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
    fecha_adquisicion = models.DateTimeField()
    id_tipo_herramienta = models.ForeignKey(tipo_herramienta, on_delete=models.CASCADE)
