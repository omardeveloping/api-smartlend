from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class rol_usuarios(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=20)
    desc = models.CharField(max_length=100)
    permisos = models.CharField(max_length=200)

class carrera(models.Model):
    id_carrera = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

class Usuario(AbstractUser):
    username = None
    EMAIL_FIELD = 'correo'
    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['rut', 'nombres', 'apellidos', 'id_carrera']
    first_name = None
    last_name = None

    rut = models.CharField(max_length=12, unique=True)
    embedding = models.TextField(null=True, blank=True)
    nombres = models.CharField(max_length=35)
    apellidos = models.CharField(max_length=35)
    id_carrera = models.ForeignKey(carrera, on_delete=models.CASCADE, null=True, blank=True)
    correo = models.EmailField(max_length=50, unique=True)
    id_rol = models.ForeignKey(rol_usuarios, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.correo or self.rut

    def save(self, *args, **kwargs):
        # Keep Django's default email field in sync with correo.
        self.email = self.correo
        super().save(*args, **kwargs)
