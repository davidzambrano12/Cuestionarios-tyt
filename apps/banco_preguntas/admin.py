from django.contrib import admin

from .models import Categoria, OpcionRespuesta, Pregunta


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


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "creado_en")
    search_fields = ("nombre",)
