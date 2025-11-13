from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario, rol_usuarios


@admin.register(rol_usuarios)
class RolUsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_rol', 'nombre')
    search_fields = ('nombre',)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('correo', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Informacion adicional', {
            'fields': ('rut', 'embedding', 'nombres', 'apellidos', 'id_carrera', 'id_rol'),
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('correo', 'password1', 'password2', 'rut', 'embedding', 'nombres', 'apellidos', 'id_carrera', 'id_rol'),
        }),
    )
    list_display = ('correo', 'rut', 'id_rol', 'is_staff')
    search_fields = ('correo', 'rut', 'nombres', 'apellidos')
    ordering = ('correo',)
