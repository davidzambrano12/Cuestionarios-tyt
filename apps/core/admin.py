from django.contrib import admin
from .models import ConfiguracionSistema, PermisoSistema, PerfilUsuario, Rol


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


@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = ("nombre_sistema", "institucion", "correo_soporte", "actualizado_en")

    def has_add_permission(self, request):
        return not ConfiguracionSistema.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
