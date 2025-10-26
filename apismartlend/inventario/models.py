from django.db import models

# Create your models here.
class estado_herramienta(models.Model):
    id_estado_herramienta = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=20)

class categoria_herramienta(models.Model):
    id_categoria_herramienta = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

class herramienta(models.Model):
    id_herramienta = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    desc = models.CharField(max_length=200)
    id_estado = models.ForeignKey(estado_herramienta, on_delete=models.CASCADE)
    id_categoria = models.ForeignKey(categoria_herramienta, on_delete=models.CASCADE)