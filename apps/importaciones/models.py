"""Módulo B: bitácora de cada importación de preguntas."""
from django.db import models


class Importacion(models.Model):
    RESULTADO_CHOICES = [
        ("exitosa", "Exitosa"),
        ("parcial", "Parcial"),
        ("fallida", "Fallida"),
    ]

    id = models.BigAutoField(primary_key=True)
    cuestionario = models.ForeignKey(
        "cuestionarios.Cuestionario", on_delete=models.SET_NULL, db_column="cuestionario_id",
        related_name="importaciones", blank=True, null=True,
    )
    nombre_archivo = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    total_filas = models.IntegerField(default=0)
    filas_validas = models.IntegerField(default=0)
    filas_duplicadas = models.IntegerField(default=0)
    filas_con_error = models.IntegerField(default=0)
    resultado = models.CharField(max_length=10, choices=RESULTADO_CHOICES)

    class Meta:
        db_table = "importaciones"
