"""
Serializers de la API. Solo traducen modelos ↔ JSON y validan la forma de los
datos; las reglas de negocio (huella anti-duplicados, calificación, alcance de
cada rol) viven en los servicios de cada app y se reutilizan desde las vistas.
"""
from decimal import Decimal

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.banco_preguntas.models import Categoria, OpcionRespuesta, Pregunta
from apps.cuestionarios.models import Cuestionario
from apps.cuestionarios.services import serializar_preguntas
from apps.evaluaciones.models import Intento
from apps.evaluaciones import services as evaluacion

# ---------------------------------------------------------------------------
# Simulacros
# ---------------------------------------------------------------------------


class SimulacroSerializer(serializers.ModelSerializer):
    estado = serializers.CharField(source="estado_temporal", help_text="Estado efectivo: borrador, programado, disponible, oculto, cerrado o archivado (combina el estado elegido por el docente con las fechas).")
    numero_preguntas = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cuestionario
        fields = [
            "id", "nombre", "descripcion", "visibilidad", "estado",
            "fecha_apertura", "fecha_cierre", "tiempo_limite_minutos", "intentos_permitidos",
            "calificacion_maxima", "calificacion_aprobacion", "permitir_revision", "numero_preguntas",
        ]


# ---------------------------------------------------------------------------
# Preguntas
# ---------------------------------------------------------------------------


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ["id", "nombre"]


class OpcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpcionRespuesta
        fields = ["id", "texto", "es_correcta", "orden"]


class PreguntaSerializer(serializers.ModelSerializer):
    categoria = CategoriaSerializer()
    opciones = serializers.SerializerMethodField()

    class Meta:
        model = Pregunta
        fields = [
            "id", "categoria", "tipo", "texto_base", "enunciado", "retroalimentacion",
            "puntaje", "activa", "opciones",
        ]

    @extend_schema_field(OpcionSerializer(many=True))
    def get_opciones(self, pregunta):
        opciones = sorted(pregunta.opciones.all(), key=lambda o: (o.orden, o.id))
        return OpcionSerializer(opciones, many=True).data


class OpcionEntradaSerializer(serializers.Serializer):
    texto = serializers.CharField(max_length=500, trim_whitespace=True)
    es_correcta = serializers.BooleanField(default=False)


class PreguntaActualizarSerializer(serializers.Serializer):
    """
    Cuerpo del PATCH: todos los campos son opcionales; los omitidos conservan su
    valor. Si se envía `opciones` se reemplazan todas (las de V/F siempre son
    «Verdadero» y «Falso»); si no, se conservan con sus ids.
    """
    categoria_id = serializers.PrimaryKeyRelatedField(
        queryset=Categoria.objects.all(), source="categoria", required=False,
        help_text="Eje temático (competencia) de la pregunta.",
    )
    tipo = serializers.ChoiceField(choices=Pregunta.TIPO_CHOICES, required=False)
    texto_base = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    enunciado = serializers.CharField(required=False, trim_whitespace=True)
    retroalimentacion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    puntaje = serializers.DecimalField(
        max_digits=6, decimal_places=2, min_value=Decimal("0.01"), required=False,
    )
    activa = serializers.BooleanField(required=False, help_text="Borrado lógico: false la oculta de nuevos simulacros.")
    opciones = OpcionEntradaSerializer(many=True, required=False)

    def validate_enunciado(self, valor):
        if not valor.strip():
            raise serializers.ValidationError("El enunciado no puede quedar vacío.")
        return valor

    def validate(self, attrs):
        pregunta: Pregunta = self.instance
        tipo = attrs.get("tipo", pregunta.tipo)
        opciones = attrs.get("opciones")
        if "tipo" in attrs and tipo != pregunta.tipo and opciones is None:
            raise serializers.ValidationError({"opciones": "Al cambiar el tipo debe enviar las nuevas opciones."})
        if opciones is None:
            return attrs

        if tipo == Pregunta.TIPO_VF:
            if len(opciones) != 2:
                raise serializers.ValidationError({"opciones": "Una pregunta Verdadero/Falso tiene exactamente 2 opciones."})
            opciones[0]["texto"], opciones[1]["texto"] = "Verdadero", "Falso"
        elif not 2 <= len(opciones) <= 4:
            raise serializers.ValidationError({"opciones": "Una pregunta de selección múltiple tiene entre 2 y 4 opciones."})
        if sum(1 for o in opciones if o["es_correcta"]) != 1:
            raise serializers.ValidationError({"opciones": "Debe haber exactamente una opción correcta."})
        textos = [o["texto"].strip().lower() for o in opciones]
        if len(set(textos)) != len(textos):
            raise serializers.ValidationError({"opciones": "Las opciones no pueden repetirse."})
        return attrs


# ---------------------------------------------------------------------------
# Intentos y resultados
# ---------------------------------------------------------------------------


class IntentoCrearSerializer(serializers.Serializer):
    simulacro_id = serializers.IntegerField(help_text="Id del simulacro (GET /api/simulacros/).")
    curso_id = serializers.IntegerField(
        required=False, allow_null=True,
        help_text="Solo si el estudiante tiene varios cursos en los que cuenta el simulacro.",
    )
    respuestas = serializers.DictField(
        child=serializers.IntegerField(allow_null=True), required=False,
        help_text=(
            "Opcional. {pregunta_id: opcion_id}. Si se envía, el intento se califica y "
            "finaliza en la misma solicitud; las preguntas omitidas cuentan como no respondidas."
        ),
    )


class FinalizarSerializer(serializers.Serializer):
    respuestas = serializers.DictField(
        child=serializers.IntegerField(allow_null=True),
        help_text="{pregunta_id: opcion_id}. Las preguntas omitidas cuentan como no respondidas.",
    )


class SimulacroResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    calificacion_maxima = serializers.DecimalField(max_digits=5, decimal_places=2)


class OpcionSinClaveSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    texto = serializers.CharField()


class PreguntaExamenSerializer(serializers.Serializer):
    """Pregunta tal como la ve el estudiante: sin la opción correcta ni la retroalimentación."""
    id = serializers.IntegerField()
    categoria = serializers.CharField()
    tipo = serializers.CharField()
    texto_base = serializers.CharField()
    enunciado = serializers.CharField()
    puntaje = serializers.CharField()
    opciones = OpcionSinClaveSerializer(many=True)


class ResultadoSerializer(serializers.ModelSerializer):
    simulacro = SimulacroResumenSerializer(source="cuestionario")
    curso = serializers.SerializerMethodField()
    periodo = serializers.SerializerMethodField()
    dictamen = serializers.SerializerMethodField()

    class Meta:
        model = Intento
        fields = [
            "id", "simulacro", "participante_nombre", "participante_codigo", "curso", "periodo",
            "estado", "fecha_inicio", "fecha_fin", "duracion_segundos",
            "puntaje_obtenido", "puntaje_total_posible", "calificacion", "aprobado", "dictamen",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_curso(self, intento):
        return intento.curso.nombre if intento.curso_id else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_periodo(self, intento):
        return intento.periodo.nombre if intento.periodo_id else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_dictamen(self, intento):
        return evaluacion.dictamen_intento(intento, intento.cuestionario)


class IntentoSerializer(ResultadoSerializer):
    """Intento recién registrado: si sigue en curso trae el tiempo restante y sus preguntas."""
    segundos_restantes = serializers.SerializerMethodField()
    preguntas = serializers.SerializerMethodField()

    class Meta(ResultadoSerializer.Meta):
        fields = ResultadoSerializer.Meta.fields + ["segundos_restantes", "preguntas"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_segundos_restantes(self, intento):
        return evaluacion.segundos_restantes(intento) if intento.estado == "en_progreso" else None

    @extend_schema_field(PreguntaExamenSerializer(many=True))
    def get_preguntas(self, intento):
        if intento.estado != "en_progreso":
            return []
        return serializar_preguntas(intento.cuestionario, semilla=intento.id, incluir_claves=False)


class CursoOpcionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class IntentoRechazadoSerializer(serializers.Serializer):
    detail = serializers.CharField()
    cursos = CursoOpcionSerializer(many=True, required=False, help_text="Cursos entre los que debe elegir (curso_id).")


# ---------------------------------------------------------------------------
# Reportes (solo para documentar la respuesta: los datos salen de reportes.consultas)
# ---------------------------------------------------------------------------


class IndicadoresSerializer(serializers.Serializer):
    estudiantes = serializers.IntegerField()
    intentos = serializers.IntegerField(help_text="Intentos terminados (finalizados o vencidos) con nota.")
    en_progreso = serializers.IntegerField()
    promedio = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True, help_text="Sobre 5,0.")
    minima = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    maxima = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    aprobados = serializers.IntegerField()
    no_aprobados = serializers.IntegerField()
    porcentaje_aprobacion = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class FilaPeriodoSerializer(serializers.Serializer):
    anio = serializers.IntegerField(allow_null=True)
    periodo = serializers.CharField()
    intentos = serializers.IntegerField()
    estudiantes = serializers.IntegerField()
    promedio = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    porcentaje_aprobacion = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class FilaCursoSerializer(serializers.Serializer):
    curso_id = serializers.IntegerField(allow_null=True)
    curso = serializers.CharField()
    periodo = serializers.CharField()
    intentos = serializers.IntegerField()
    estudiantes = serializers.IntegerField()
    promedio = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    minima = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    maxima = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    porcentaje_aprobacion = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class FilaEjeSerializer(serializers.Serializer):
    eje = serializers.CharField()
    registradas = serializers.IntegerField()
    respondidas = serializers.IntegerField()
    aciertos = serializers.IntegerField()
    errores = serializers.IntegerField()
    omitidas = serializers.IntegerField()
    porcentaje_aciertos = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class FiltroAplicadoSerializer(serializers.Serializer):
    filtro = serializers.CharField()
    valor = serializers.CharField()


class ReporteSerializer(serializers.Serializer):
    filtros = FiltroAplicadoSerializer(many=True, help_text="Filtros aplicados, con nombres legibles.")
    avisos = serializers.ListField(child=serializers.CharField(), help_text="Filtros incompatibles que se quitaron.")
    indicadores = IndicadoresSerializer()
    por_periodo = FilaPeriodoSerializer(many=True)
    por_curso = FilaCursoSerializer(many=True)
    por_eje = FilaEjeSerializer(many=True)


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
