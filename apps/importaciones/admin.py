from django.contrib import admin

from .models import Importacion


@admin.register(Importacion)
class ImportacionAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre_archivo", "fecha", "total_filas", "filas_validas", "filas_duplicadas", "filas_con_error", "resultado")
    list_filter = ("resultado",)
