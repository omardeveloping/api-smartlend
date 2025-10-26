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
        (None, {'fields': ('username', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Informacion adicional', {
            'fields': ('rut', 'embedding', 'nombres', 'apellidos', 'carrera', 'correo', 'id_rol'),
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'rut', 'embedding', 'nombres', 'apellidos', 'carrera', 'correo', 'id_rol'),
        }),
    )
    list_display = ('username', 'rut', 'correo', 'id_rol', 'is_staff')
    search_fields = ('username', 'rut', 'correo', 'nombres', 'apellidos')
    ordering = ('username',)
