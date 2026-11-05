from django.contrib import admin
from .models import PermisoSistema, Rol, PerfilUsuario


@admin.register(PermisoSistema)
class PermisoSistemaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "modulo")
    list_filter = ("modulo",)
    search_fields = ("codigo", "nombre", "descripcion")


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "activo", "es_sistema", "creado_en")
    list_filter = ("activo", "es_sistema")
    search_fields = ("nombre", "codigo")
    filter_horizontal = ("permisos",)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("user", "rol", "codigo_institucional", "programa_academico", "creado_en")
    list_filter = ("rol",)
    search_fields = ("user__username", "user__email", "codigo_institucional")
