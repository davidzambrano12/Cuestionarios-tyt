from django.contrib import admin
from .models import (
    Categoria,
    Pregunta,
    OpcionRespuesta,
    Cuestionario,
    CuestionarioPregunta,
    Importacion,
    Intento,
    RespuestaIntento,
)


class OpcionRespuestaInline(admin.TabularInline):
    model = OpcionRespuesta
    extra = 2


@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ("id", "enunciado_corto", "categoria", "tipo", "puntaje", "activa")
    list_filter = ("categoria", "tipo", "activa")
    search_fields = ("enunciado", "texto_base")
    inlines = [OpcionRespuestaInline]

    def enunciado_corto(self, obj):
        return obj.enunciado[:60]


class CuestionarioPreguntaInline(admin.TabularInline):
    model = CuestionarioPregunta
    extra = 1


@admin.register(Cuestionario)
class CuestionarioAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "estado", "fecha_apertura", "fecha_cierre", "tiempo_limite_minutos", "calificacion_maxima")
    list_filter = ("estado",)
    search_fields = ("nombre",)
    inlines = [CuestionarioPreguntaInline]


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "creado_en")
    search_fields = ("nombre",)


@admin.register(Importacion)
class ImportacionAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre_archivo", "fecha", "total_filas", "filas_validas", "filas_duplicadas", "filas_con_error", "resultado")
    list_filter = ("resultado",)


@admin.register(Intento)
class IntentoAdmin(admin.ModelAdmin):
    list_display = ("id", "participante_nombre", "participante_codigo", "cuestionario", "calificacion", "aprobado", "estado", "fecha_inicio")
    list_filter = ("estado", "aprobado", "cuestionario")
    search_fields = ("participante_nombre", "participante_codigo")


@admin.register(RespuestaIntento)
class RespuestaIntentoAdmin(admin.ModelAdmin):
    list_display = ("id", "intento", "pregunta", "es_correcta", "puntaje_obtenido")
    list_filter = ("es_correcta",)
