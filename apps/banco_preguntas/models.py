"""Módulo A: categorías (competencias), preguntas y sus opciones de respuesta."""
from django.db import models


class Categoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categorias"

    def __str__(self):
        return self.nombre


class Pregunta(models.Model):
    TIPO_MULTIPLE = "MULTIPLE"
    TIPO_VF = "V_F"
    TIPO_CHOICES = [
        (TIPO_MULTIPLE, "Selección múltiple"),
        (TIPO_VF, "Verdadero / Falso"),
    ]

    id = models.BigAutoField(primary_key=True)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.DO_NOTHING, db_column="categoria_id",
        related_name="preguntas",
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    texto_base = models.TextField(blank=True, null=True)
    enunciado = models.TextField()
    retroalimentacion = models.TextField(blank=True, null=True)
    puntaje = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    # SHA2(enunciado + opciones normalizadas) — evita duplicados (RF05 / UNIQUE)
    huella_contenido = models.CharField(max_length=64, unique=True, blank=True, null=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "preguntas"

    def __str__(self):
        return self.enunciado[:60]


class OpcionRespuesta(models.Model):
    id = models.BigAutoField(primary_key=True)
    pregunta = models.ForeignKey(
        Pregunta, on_delete=models.CASCADE, db_column="pregunta_id",
        related_name="opciones",
    )
    texto = models.CharField(max_length=500)
    es_correcta = models.BooleanField(default=False)
    orden = models.SmallIntegerField(default=0)

    class Meta:
        db_table = "opciones_respuesta"

    def __str__(self):
        return self.texto
