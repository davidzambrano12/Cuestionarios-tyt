"""
Estructura académica: períodos, cursos (grupos) y matrículas.

Ruta de datos para los reportes:
    PeriodoAcademico (año, número) ─< Curso ─< Matricula >─ User (estudiante)
                                       │
                                       └─< Intento (curso en el que se presentó)

Cada intento guarda el curso del estudiante en el momento de presentarlo,
de modo que los reportes históricos no cambian si después lo matriculan en
otro curso.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class PeriodoAcademico(models.Model):
    id = models.BigAutoField(primary_key=True)
    anio = models.PositiveSmallIntegerField("año")
    numero = models.PositiveSmallIntegerField("número", help_text="1 o 2 para semestres; 1 a 4 para trimestres.")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    class Meta:
        db_table = "periodos_academicos"
        ordering = ["-anio", "-numero"]
        verbose_name = "período académico"
        verbose_name_plural = "períodos académicos"
        constraints = [
            models.UniqueConstraint(fields=["anio", "numero"], name="uq_periodo_anio_numero"),
            models.CheckConstraint(condition=Q(fecha_fin__gt=F("fecha_inicio")), name="chk_periodo_fechas"),
            models.CheckConstraint(condition=Q(numero__gte=1) & Q(numero__lte=4), name="chk_periodo_numero"),
        ]

    @property
    def nombre(self) -> str:
        return f"{self.anio}-{self.numero}"

    def __str__(self):
        return self.nombre


class Curso(models.Model):
    """Una asignatura dictada a un grupo en un período (p. ej. Electiva Profesional III, grupo 01, 2026-2)."""
    id = models.BigAutoField(primary_key=True)
    periodo = models.ForeignKey(
        PeriodoAcademico, on_delete=models.PROTECT, db_column="periodo_id", related_name="cursos",
    )
    asignatura = models.CharField(max_length=150, help_text="Ej.: Electiva Profesional III – Frameworks")
    grupo = models.CharField(max_length=10, default="01", help_text="Ej.: 01, 02, A")
    programa = models.CharField(max_length=150, default="Ingeniería de Sistemas")
    semestre = models.PositiveSmallIntegerField(blank=True, null=True, help_text="Semestre del plan de estudios (1 a 12).")
    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, db_column="docente_id",
        related_name="cursos_a_cargo", blank=True, null=True,
        help_text="Docente que gestiona el curso y consulta sus resultados.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "cursos"
        ordering = ["-periodo__anio", "-periodo__numero", "asignatura", "grupo"]
        constraints = [
            models.UniqueConstraint(fields=["periodo", "asignatura", "grupo"], name="uq_curso_periodo_asignatura_grupo"),
            models.CheckConstraint(condition=Q(semestre__isnull=True) | (Q(semestre__gte=1) & Q(semestre__lte=12)),
                                   name="chk_curso_semestre"),
        ]

    @property
    def nombre(self) -> str:
        """Nombre corto para filtros y reportes: «Asignatura · G01»."""
        return f"{self.asignatura} · G{self.grupo}"

    def __str__(self):
        return f"{self.nombre} ({self.periodo})"


class Matricula(models.Model):
    id = models.BigAutoField(primary_key=True)
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, db_column="curso_id", related_name="matriculas")
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="estudiante_id", related_name="matriculas",
    )
    fecha_matricula = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "matriculas"
        verbose_name = "matrícula"
        constraints = [
            models.UniqueConstraint(fields=["curso", "estudiante"], name="uq_matricula_curso_estudiante"),
        ]

    def __str__(self):
        return f"{self.estudiante} en {self.curso}"
