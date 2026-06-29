from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import DirectorCarrera, Usuario, rol_usuarios, carrera


@admin.register(rol_usuarios)
class RolUsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_rol', 'nombre', 'codigo')
    search_fields = ('nombre', 'codigo')


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('correo', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'baneado_en')}),
        ('Informacion adicional', {
            'fields': ('rut', 'embedding', 'nombres', 'apellidos', 'id_carrera', 'id_rol', 'esta_baneado', 'aviso_ban_enviado'),
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('correo', 'password1', 'password2', 'rut', 'embedding', 'nombres', 'apellidos', 'id_carrera', 'id_rol'),
        }),
    )
    list_display = ('correo', 'rut', 'id_rol', 'esta_baneado', 'is_staff')
    search_fields = ('correo', 'rut', 'nombres', 'apellidos')
    ordering = ('correo',)
    readonly_fields = ('baneado_en',)


@admin.register(DirectorCarrera)
class DirectorCarreraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'carrera')
    search_fields = ('nombre', 'correo', 'carrera__nombre')


@admin.register(carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('id_carrera', 'nombre')
    search_fields = ('nombre',)
