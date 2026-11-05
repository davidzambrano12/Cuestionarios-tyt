"""Módulo C: cuestionarios y su asignación ordenada de preguntas (N:M)."""
from django.conf import settings
from django.utils import timezone
from django.db import models


class Cuestionario(models.Model):
    ESTADO_CHOICES = [
        ("borrador", "Borrador"),
        ("programado", "Programado"),
        ("disponible", "Disponible"),
        ("cerrado", "Cerrado"),
    ]

    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    fecha_apertura = models.DateTimeField()
    fecha_cierre = models.DateTimeField()
    tiempo_limite_minutos = models.IntegerField()
    intentos_permitidos = models.IntegerField(default=5)
    calificacion_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    calificacion_aprobacion = models.DecimalField(max_digits=5, decimal_places=2)
    mezclar_preguntas = models.BooleanField(default=False)
    mezclar_respuestas = models.BooleanField(default=False)
    permitir_revision = models.BooleanField(default=True)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="borrador")

    # Quién lo creó y quién puede presentarlo
    INSTITUCIONAL = "institucional"
    PRIVADO = "privado"
    VISIBILIDAD_CHOICES = [
        (INSTITUCIONAL, "Institucional: cualquier estudiante"),
        (PRIVADO, "De curso: solo los cursos asignados"),
    ]
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, db_column="creado_por_id",
        related_name="cuestionarios_creados", blank=True, null=True,
    )
    visibilidad = models.CharField(max_length=13, choices=VISIBILIDAD_CHOICES, default=PRIVADO)
    cursos = models.ManyToManyField(
        "academico.Curso", related_name="cuestionarios", blank=True, db_table="cuestionario_cursos",
    )

    class Meta:
        db_table = "cuestionarios"

    @property
    def es_institucional(self) -> bool:
        return self.visibilidad == self.INSTITUCIONAL

    def __str__(self):
        return self.nombre

    @property
    def estado_temporal(self):
        """Retorna el estado dinámico evaluando las fechas del servidor."""
        if self.estado == "borrador":
            return "borrador"
        ahora = timezone.now()
        if self.estado == "cerrado" or (self.fecha_cierre and ahora > self.fecha_cierre):
            return "cerrado"
        if self.fecha_apertura and ahora < self.fecha_apertura:
            return "programado"
        if self.estado == "disponible":
            return "disponible"
        return self.estado

    @property
    def esta_vigente(self):
        """True si el cuestionario está publicado y dentro del rango de apertura y cierre."""
        if self.estado != "disponible":
            return False
        ahora = timezone.now()
        if not self.fecha_apertura or not self.fecha_cierre:
            return True
        return self.fecha_apertura <= ahora <= self.fecha_cierre

    @property
    def esta_vencido(self):
        """True si el plazo de entrega ya expiró o fue forzado a cerrado."""
        if self.estado == "cerrado":
            return True
        if self.fecha_cierre and timezone.now() > self.fecha_cierre:
            return True
        return False

    @property
    def tiempo_restante_info(self):
        """Genera un diccionario semántico para los badges y alertas de tiempo."""
        if self.estado == "borrador":
            return {"texto": "Borrador sin publicar", "clase": "badge-warning", "urgencia": "baja"}
        ahora = timezone.now()
        if self.esta_vencido:
            return {"texto": "Plazo finalizado", "clase": "badge-danger", "urgencia": "vencido"}
        if self.fecha_apertura and ahora < self.fecha_apertura:
            delta = self.fecha_apertura - ahora
            if delta.days == 0:
                horas = max(1, int(delta.total_seconds() // 3600))
                return {"texto": f"Abre hoy en ~{horas}h", "clase": "badge-info", "urgencia": "proximo"}
            return {"texto": f"Abre en {delta.days} días", "clase": "badge-info", "urgencia": "proximo"}
        if not self.fecha_cierre:
            return {"texto": "Sin fecha límite", "clase": "badge-success", "urgencia": "baja"}
        delta = self.fecha_cierre - ahora
        total_seg = delta.total_seconds()
        if total_seg <= 3600:
            return {"texto": "Cierra en menos de 1h", "clase": "badge-danger", "urgencia": "critica"}
        elif total_seg < 86400:
            horas = int(total_seg // 3600)
            return {"texto": f"Cierra hoy (~{horas}h restantes)", "clase": "badge-warning", "urgencia": "alta"}
        elif delta.days <= 3:
            return {"texto": f"Quedan {delta.days} días", "clase": "badge-warning", "urgencia": "media"}
        else:
            return {"texto": f"Cierra en {delta.days} días", "clase": "badge-success", "urgencia": "baja"}


class CuestionarioPregunta(models.Model):
    id = models.BigAutoField(primary_key=True)
    cuestionario = models.ForeignKey(
        Cuestionario, on_delete=models.CASCADE, db_column="cuestionario_id",
        related_name="cuestionario_preguntas",
    )
    pregunta = models.ForeignKey(
        "banco_preguntas.Pregunta", on_delete=models.DO_NOTHING, db_column="pregunta_id",
        related_name="cuestionario_preguntas",
    )
    orden = models.IntegerField(default=0)
    # Si es NULL, en la calificación prevalece preguntas.puntaje
    puntaje_asignado = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = "cuestionario_preguntas"
        unique_together = (("cuestionario", "pregunta"),)
