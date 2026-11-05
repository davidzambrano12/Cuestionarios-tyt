"""Módulo D: intentos de los participantes y sus respuestas."""
from django.db import models


class Intento(models.Model):
    ESTADO_CHOICES = [
        ("en_progreso", "En progreso"),
        ("finalizado", "Finalizado"),
        ("vencido", "Vencido"),
    ]

    id = models.BigAutoField(primary_key=True)
    cuestionario = models.ForeignKey(
        "cuestionarios.Cuestionario", on_delete=models.CASCADE, db_column="cuestionario_id",
        related_name="intentos",
    )
    # Curso del estudiante al presentar el intento (base de los reportes por período y curso)
    curso = models.ForeignKey(
        "academico.Curso", on_delete=models.PROTECT, db_column="curso_id",
        related_name="intentos", blank=True, null=True,
    )
    # Período según la fecha del intento: cuenta en los reportes aunque no tenga curso
    periodo = models.ForeignKey(
        "academico.PeriodoAcademico", on_delete=models.PROTECT, db_column="periodo_id",
        related_name="intentos", blank=True, null=True,
    )
    participante_nombre = models.CharField(max_length=150)
    participante_codigo = models.CharField(max_length=50)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    duracion_segundos = models.IntegerField(blank=True, null=True)
    puntaje_obtenido = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    puntaje_total_posible = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    calificacion = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    aprobado = models.BooleanField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="en_progreso")

    class Meta:
        db_table = "intentos"

    def __str__(self):
        return f"Intento #{self.id} - {self.participante_nombre} ({self.cuestionario.nombre})"


class RespuestaIntento(models.Model):
    id = models.BigAutoField(primary_key=True)
    intento = models.ForeignKey(
        Intento, on_delete=models.CASCADE, db_column="intento_id",
        related_name="respuestas",
    )
    pregunta = models.ForeignKey(
        "banco_preguntas.Pregunta", on_delete=models.CASCADE, db_column="pregunta_id",
        related_name="respuestas_intento",
    )
    opcion_seleccionada = models.ForeignKey(
        "banco_preguntas.OpcionRespuesta", on_delete=models.SET_NULL, db_column="opcion_seleccionada_id",
        blank=True, null=True,
    )
    es_correcta = models.BooleanField(blank=True, null=True)
    puntaje_obtenido = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    marcada_para_revision = models.BooleanField(default=False)

    class Meta:
        db_table = "respuestas_intento"

    def __str__(self):
        return f"Resp Intento #{self.intento_id} - Pregunta #{self.pregunta_id}"
