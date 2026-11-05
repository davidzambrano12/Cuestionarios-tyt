from django.contrib import admin

from .models import Intento, RespuestaIntento


@admin.register(Intento)
class IntentoAdmin(admin.ModelAdmin):
    list_display = ("id", "participante_nombre", "participante_codigo", "cuestionario", "calificacion", "aprobado", "estado", "fecha_inicio")
    list_filter = ("estado", "aprobado", "cuestionario")
    search_fields = ("participante_nombre", "participante_codigo")


@admin.register(RespuestaIntento)
class RespuestaIntentoAdmin(admin.ModelAdmin):
    list_display = ("id", "intento", "pregunta", "es_correcta", "puntaje_obtenido")
    list_filter = ("es_correcta",)
