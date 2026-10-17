"""
Modelos mapeados a las tablas que ya existen en MariaDB (creadas por el
script pruebas-tyt.sql). Se usan `managed = False` porque la base de datos
y sus triggers (R05, R06) ya están creados por ese script: Django NO debe
intentar crear ni alterar estas tablas con sus propias migraciones.

Si prefieres que Django SÍ administre las tablas (generando sus propias
migraciones), quita `managed = False` de cada Meta y ajusta el
`db_table` según lo que generen esas migraciones.
"""
from django.db import models


class Categoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
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
        managed = False
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
        managed = False
        db_table = "opciones_respuesta"

    def __str__(self):
        return self.texto


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
    intentos_permitidos = models.IntegerField()
    calificacion_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    calificacion_aprobacion = models.DecimalField(max_digits=5, decimal_places=2)
    mezclar_preguntas = models.BooleanField(default=False)
    mezclar_respuestas = models.BooleanField(default=False)
    permitir_revision = models.BooleanField(default=True)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="borrador")

    class Meta:
        managed = False
        db_table = "cuestionarios"

    def __str__(self):
        return self.nombre


class CuestionarioPregunta(models.Model):
    id = models.BigAutoField(primary_key=True)
    cuestionario = models.ForeignKey(
        Cuestionario, on_delete=models.CASCADE, db_column="cuestionario_id",
        related_name="cuestionario_preguntas",
    )
    pregunta = models.ForeignKey(
        Pregunta, on_delete=models.DO_NOTHING, db_column="pregunta_id",
        related_name="cuestionario_preguntas",
    )
    orden = models.IntegerField(default=0)
    # Si es NULL, en la calificación prevalece preguntas.puntaje
    puntaje_asignado = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "cuestionario_preguntas"
        unique_together = (("cuestionario", "pregunta"),)


class Importacion(models.Model):
    RESULTADO_CHOICES = [
        ("exitosa", "Exitosa"),
        ("parcial", "Parcial"),
        ("fallida", "Fallida"),
    ]

    id = models.BigAutoField(primary_key=True)
    cuestionario = models.ForeignKey(
        Cuestionario, on_delete=models.SET_NULL, db_column="cuestionario_id",
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
        managed = False
        db_table = "importaciones"
