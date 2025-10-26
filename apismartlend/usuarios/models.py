from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class rol_usuarios(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=20)
    desc = models.CharField(max_length=100)
    permisos = models.CharField(max_length=200)

class Usuario(AbstractUser):
    EMAIL_FIELD = 'correo'
    REQUIRED_FIELDS = ['correo', 'rut', 'nombres', 'apellidos', 'carrera', 'embedding']
    first_name = None
    last_name = None

    rut = models.CharField(max_length=12, unique=True)
    embedding = models.CharField(max_length=512)
    nombres = models.CharField(max_length=35)
    apellidos = models.CharField(max_length=35)
    carrera = models.CharField(max_length=50)
    correo = models.EmailField(max_length=50, unique=True)
    id_rol = models.ForeignKey(rol_usuarios, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.username or self.rut

    def save(self, *args, **kwargs):
        # Keep Django's default email field in sync with correo.
        self.email = self.correo
        super().save(*args, **kwargs)
