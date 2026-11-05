from django.contrib import admin

from .models import Cuestionario, CuestionarioPregunta


class CuestionarioPreguntaInline(admin.TabularInline):
    model = CuestionarioPregunta
    extra = 1


@admin.register(Cuestionario)
class CuestionarioAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "estado", "fecha_apertura", "fecha_cierre", "tiempo_limite_minutos", "calificacion_maxima")
    list_filter = ("estado",)
    search_fields = ("nombre",)
    inlines = [CuestionarioPreguntaInline]
