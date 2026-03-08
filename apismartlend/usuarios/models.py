from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class rol_usuarios(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=20)
    codigo = models.CharField(max_length=30, blank=True, default='', db_index=True)
    desc = models.CharField(max_length=100)
    permisos = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        codigo_limpio = (self.codigo or '').strip()
        if not codigo_limpio:
            codigo_limpio = (self.nombre or '').strip().upper()
        self.codigo = codigo_limpio.upper()
        super().save(*args, **kwargs)


class carrera(models.Model):
    id_carrera = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre


class DirectorCarrera(models.Model):
    id_director = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    correo = models.EmailField(max_length=100)
    carrera = models.OneToOneField(carrera, on_delete=models.CASCADE, related_name='director')

    def __str__(self):
        return f'{self.nombre} ({self.carrera.nombre})'


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
    esta_baneado = models.BooleanField(default=False)
    baneado_en = models.DateTimeField(null=True, blank=True)
    aviso_ban_enviado = models.BooleanField(default=False)

    def __str__(self):
        return self.correo or self.rut

    def save(self, *args, **kwargs):
        # Keep Django's default email field in sync with correo.
        self.email = self.correo
        super().save(*args, **kwargs)
