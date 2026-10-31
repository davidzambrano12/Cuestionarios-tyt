from django.utils import timezone
"""
Modelos mapeados a las tablas que ya existen en MariaDB (creadas por el
script pruebas-tyt.sql). Se usan `managed = False` porque la base de datos
y sus triggers (R05, R06) ya están creados por ese script: Django NO debe
intentar crear ni alterar estas tablas con sus propias migraciones.

Si prefieres que Django SÍ administre las tablas (generando sus propias
migraciones), quita `managed = False` de cada Meta y ajusta el
`db_table` según lo que generen esas migraciones.
"""
# pyrefly: ignore[missing-import]
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

    class Meta:
        
        db_table = "cuestionarios"

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
        Pregunta, on_delete=models.DO_NOTHING, db_column="pregunta_id",
        related_name="cuestionario_preguntas",
    )
    orden = models.IntegerField(default=0)
    # Si es NULL, en la calificación prevalece preguntas.puntaje
    puntaje_asignado = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    class Meta:
     
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
       
        db_table = "importaciones"


class Intento(models.Model):
    ESTADO_CHOICES = [
        ("en_progreso", "En progreso"),
        ("finalizado", "Finalizado"),
        ("vencido", "Vencido"),
    ]

    id = models.BigAutoField(primary_key=True)
    cuestionario = models.ForeignKey(
        Cuestionario, on_delete=models.CASCADE, db_column="cuestionario_id",
        related_name="intentos",
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
        Pregunta, on_delete=models.CASCADE, db_column="pregunta_id",
        related_name="respuestas_intento",
    )
    opcion_seleccionada = models.ForeignKey(
        OpcionRespuesta, on_delete=models.SET_NULL, db_column="opcion_seleccionada_id",
        blank=True, null=True,
    )
    es_correcta = models.BooleanField(blank=True, null=True)
    puntaje_obtenido = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    marcada_para_revision = models.BooleanField(default=False)

    class Meta:
       
        db_table = "respuestas_intento"

    def __str__(self):
        return f"Resp Intento #{self.intento_id} - Pregunta #{self.pregunta_id}"
