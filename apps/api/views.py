"""
Vistas de la API REST. Cada una delega en los servicios de su módulo, los
mismos que usan las pantallas web, así la API y la interfaz aplican las mismas
reglas de permisos, alcance por rol, deduplicación y calificación.

Autenticación: JWT (`Authorization: Bearer <access>`, se obtiene en
POST /api/auth/token/) o la sesión del navegador.
"""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api import serializers as s
from apps.api.permisos import EsEstudiante, requiere
from apps.banco_preguntas import services as banco
from apps.banco_preguntas.models import Pregunta
from apps.core.services.acceso import codigo_participante, es_dueno_del_intento, es_personal_docente, puede_auditar_resultados
from apps.cuestionarios import acceso
from apps.cuestionarios.models import Cuestionario
from apps.evaluaciones import services as evaluacion
from apps.evaluaciones.models import Intento
from apps.reportes import consultas

NO_AUTENTICADO = OpenApiResponse(s.ErrorSerializer, description="Falta el token o expiró.")
SIN_PERMISO = OpenApiResponse(s.ErrorSerializer, description="El rol del usuario no tiene permiso para esta operación.")
NO_EXISTE = OpenApiResponse(s.ErrorSerializer, description="El recurso no existe.")


# ---------------------------------------------------------------------------
# Simulacros
# ---------------------------------------------------------------------------

@extend_schema(
    tags=["Simulacros"],
    summary="Listar simulacros disponibles",
    description=(
        "Estudiante: los simulacros publicados que puede presentar (institucionales y los de "
        "sus cursos del período vigente) que aún no han cerrado.\n\n"
        "Docente o administrador: los que gestiona más los institucionales."
    ),
    responses={200: s.SimulacroSerializer(many=True), 401: NO_AUTENTICADO},
)
class SimulacroListView(generics.ListAPIView):
    serializer_class = s.SimulacroSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if es_personal_docente(user):
            qs = acceso.visibles_para_docente(user)
        else:
            qs = acceso.visibles_para_estudiante(user).filter(estado="disponible", fecha_cierre__gte=timezone.now())
        return (
            qs.annotate(numero_preguntas=Count("cuestionario_preguntas", distinct=True))
            .order_by("fecha_cierre", "id")
        )


# ---------------------------------------------------------------------------
# Preguntas
# ---------------------------------------------------------------------------

def _preguntas():
    return Pregunta.objects.select_related("categoria").prefetch_related("opciones")


@extend_schema(
    tags=["Preguntas"],
    summary="Consultar preguntas autorizadas",
    description="Banco de preguntas con sus opciones y la respuesta correcta. Requiere el permiso `preguntas.gestionar` (docente o administrador).",
    parameters=[
        OpenApiParameter("categoria", OpenApiTypes.INT, description="Id del eje temático."),
        OpenApiParameter("tipo", OpenApiTypes.STR, enum=["MULTIPLE", "V_F"]),
        OpenApiParameter("activa", OpenApiTypes.BOOL, description="true: solo activas; false: solo desactivadas."),
        OpenApiParameter("q", OpenApiTypes.STR, description="Texto a buscar en el enunciado."),
    ],
    responses={200: s.PreguntaSerializer(many=True), 401: NO_AUTENTICADO, 403: SIN_PERMISO},
)
class PreguntaListView(generics.ListAPIView):
    serializer_class = s.PreguntaSerializer
    permission_classes = [requiere("preguntas.gestionar")]

    def get_queryset(self):
        qs = _preguntas().order_by("-id")
        params = self.request.query_params
        if params.get("categoria", "").isdigit():
            qs = qs.filter(categoria_id=params["categoria"])
        if params.get("tipo") in (Pregunta.TIPO_MULTIPLE, Pregunta.TIPO_VF):
            qs = qs.filter(tipo=params["tipo"])
        if params.get("activa") in ("true", "false"):
            qs = qs.filter(activa=params["activa"] == "true")
        if params.get("q"):
            qs = qs.filter(Q(enunciado__icontains=params["q"]) | Q(texto_base__icontains=params["q"]))
        return qs


class PreguntaDetalleView(generics.RetrieveAPIView):
    serializer_class = s.PreguntaSerializer
    permission_classes = [requiere("preguntas.gestionar")]
    queryset = _preguntas()
    http_method_names = ["get", "patch", "options", "head"]

    @extend_schema(
        tags=["Preguntas"], summary="Consultar una pregunta",
        responses={200: s.PreguntaSerializer, 401: NO_AUTENTICADO, 403: SIN_PERMISO, 404: NO_EXISTE},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Preguntas"],
        summary="Actualizar una pregunta autorizada",
        description=(
            "Actualización parcial: solo cambian los campos enviados. Recalcula la huella SHA-256 "
            "y rechaza el cambio si otra pregunta queda con el mismo contenido (409).\n\n"
            "Si se envía `opciones` se reemplazan todas; si no, se conservan con sus ids, así las "
            "respuestas ya registradas no se alteran."
        ),
        request=s.PreguntaActualizarSerializer,
        responses={
            200: s.PreguntaSerializer,
            400: OpenApiResponse(description="Datos inválidos (p. ej. dos opciones correctas)."),
            401: NO_AUTENTICADO, 403: SIN_PERMISO, 404: NO_EXISTE,
            409: OpenApiResponse(s.ErrorSerializer, description="Ya existe otra pregunta con el mismo contenido."),
        },
        examples=[
            OpenApiExample("Corregir el enunciado", value={"enunciado": "¿Cuál es la idea principal del texto?"}, request_only=True),
            OpenApiExample(
                "Cambiar opciones y puntaje",
                value={"puntaje": "2.00", "opciones": [
                    {"texto": "Opción A", "es_correcta": False}, {"texto": "Opción B", "es_correcta": True},
                    {"texto": "Opción C", "es_correcta": False}, {"texto": "Opción D", "es_correcta": False},
                ]},
                request_only=True,
            ),
            OpenApiExample("Desactivar (borrado lógico)", value={"activa": False}, request_only=True),
        ],
    )
    def patch(self, request, *args, **kwargs):
        pregunta = self.get_object()
        entrada = s.PreguntaActualizarSerializer(instance=pregunta, data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data

        if "opciones" in d:
            opciones = [(o["texto"].strip(), o["es_correcta"], i) for i, o in enumerate(d["opciones"], start=1)]
        else:
            opciones = [(o.texto, o.es_correcta, o.orden) for o in pregunta.opciones.order_by("orden", "id")]
        datos = banco.DatosPregunta(
            categoria_id=d["categoria"].id if "categoria" in d else pregunta.categoria_id,
            tipo=d.get("tipo", pregunta.tipo),
            enunciado=d.get("enunciado", pregunta.enunciado).strip(),
            texto_base=(d["texto_base"] or None) if "texto_base" in d else pregunta.texto_base,
            retroalimentacion=(d["retroalimentacion"] or None) if "retroalimentacion" in d else pregunta.retroalimentacion,
            puntaje=d.get("puntaje", pregunta.puntaje),
            opciones=opciones,
        )
        try:
            banco.guardar_pregunta(datos, pregunta, reemplazar_opciones="opciones" in d)
        except banco.PreguntaDuplicada:
            return Response(
                {"detail": "Ya existe otra pregunta con el mismo contenido."}, status=status.HTTP_409_CONFLICT,
            )
        if "activa" in d and d["activa"] != pregunta.activa:
            banco.alternar_estado(pregunta)
        return Response(s.PreguntaSerializer(_preguntas().get(pk=pregunta.pk)).data)


# ---------------------------------------------------------------------------
# Intentos
# ---------------------------------------------------------------------------

def _conflicto(mensaje: str) -> Response:
    return Response({"detail": mensaje}, status=status.HTTP_409_CONFLICT)


def _intento(pk) -> Intento:
    return Intento.objects.select_related("cuestionario", "curso__periodo", "periodo").get(pk=pk)


@extend_schema(
    tags=["Intentos"],
    summary="Registrar un intento",
    description=(
        "Inicia (o reanuda) el intento del estudiante autenticado con las mismas validaciones de la "
        "sala de examen: simulacro publicado y dentro de fechas, matrícula en el curso si es de "
        "curso y límite de intentos. El temporizador corre en el servidor desde este momento.\n\n"
        "* Sin `respuestas`: devuelve el intento en curso con sus preguntas (sin la clave) y el "
        "tiempo restante; se entrega con POST /api/intentos/{id}/finalizar/.\n"
        "* Con `respuestas`: lo califica y finaliza en la misma solicitud.\n\n"
        "Solo para estudiantes: docentes y administradores reciben 403."
    ),
    request=s.IntentoCrearSerializer,
    responses={
        201: OpenApiResponse(s.IntentoSerializer, description="Intento nuevo."),
        200: OpenApiResponse(s.IntentoSerializer, description="Se reanudó un intento que seguía en curso."),
        400: OpenApiResponse(s.IntentoRechazadoSerializer, description="Fuera de fechas, sin matrícula, límite de intentos o falta elegir curso."),
        401: NO_AUTENTICADO, 403: SIN_PERMISO, 404: NO_EXISTE,
        409: OpenApiResponse(s.ErrorSerializer, description="El intento en curso ya superó el tiempo límite."),
    },
    examples=[
        OpenApiExample("Iniciar", value={"simulacro_id": 1}, request_only=True),
        OpenApiExample("Iniciar y entregar", value={"simulacro_id": 1, "respuestas": {"12": 45, "13": 50}}, request_only=True),
    ],
)
class IntentoCrearView(APIView):
    permission_classes = [EsEstudiante]

    def post(self, request):
        entrada = s.IntentoCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        cuestionario = get_object_or_404(Cuestionario, pk=d["simulacro_id"])

        resultado = evaluacion.iniciar_intento(request.user, cuestionario, curso_id=d.get("curso_id"))
        if resultado.tipo == "elegir_curso":
            return Response({
                "detail": "El simulacro cuenta en varios de tus cursos: envía curso_id con uno de estos.",
                "cursos": [{"id": c.id, "nombre": c.nombre} for c in resultado.cursos],
            }, status=status.HTTP_400_BAD_REQUEST)
        if resultado.tipo == "rechazado":
            return Response({"detail": resultado.mensaje}, status=status.HTTP_400_BAD_REQUEST)
        if resultado.tipo == "vencido":
            return _conflicto(resultado.mensaje)

        intento = resultado.intento
        if "respuestas" in d:
            intento = evaluacion.calificar_intento(intento, d["respuestas"])
        codigo = status.HTTP_201_CREATED if resultado.tipo == "nuevo" else status.HTTP_200_OK
        return Response(s.IntentoSerializer(_intento(intento.pk)).data, status=codigo)


@extend_schema(
    tags=["Intentos"],
    summary="Entregar un intento",
    description=(
        "Califica y cierra el intento en curso del estudiante autenticado con la fórmula "
        "institucional: (puntaje obtenido / puntaje total) × calificación máxima. Si ya se venció "
        "el tiempo (más la ventana de gracia) el intento se cierra como vencido y no se califica."
    ),
    request=s.FinalizarSerializer,
    responses={
        200: s.IntentoSerializer, 401: NO_AUTENTICADO,
        403: OpenApiResponse(s.ErrorSerializer, description="No es estudiante o el intento no le pertenece."),
        404: NO_EXISTE,
        409: OpenApiResponse(s.ErrorSerializer, description="El intento ya estaba cerrado o se venció el tiempo."),
    },
)
class IntentoFinalizarView(APIView):
    permission_classes = [EsEstudiante]

    def post(self, request, pk):
        intento = get_object_or_404(Intento.objects.select_related("cuestionario"), pk=pk)
        if not es_dueno_del_intento(request.user, intento):
            return Response({"detail": "Este intento no pertenece a su usuario."}, status=status.HTTP_403_FORBIDDEN)
        entrada = s.FinalizarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        if intento.estado != "en_progreso":
            return _conflicto("El intento ya fue entregado o cerrado.")
        if evaluacion.cerrar_si_vencio(intento):
            return _conflicto("El tiempo límite venció: el intento se cerró sin calificar.")
        intento = evaluacion.calificar_intento(intento, entrada.validated_data["respuestas"])
        return Response(s.IntentoSerializer(_intento(intento.pk)).data)


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------

@extend_schema(
    tags=["Resultados"],
    summary="Consultar resultados permitidos",
    description=(
        "Estudiante: solo sus propios intentos.\n\n"
        "Docente: los intentos de los cursos que tiene a cargo. Administrador: todos."
    ),
    parameters=[
        OpenApiParameter("simulacro", OpenApiTypes.INT, description="Id del simulacro."),
        OpenApiParameter("estado", OpenApiTypes.STR, enum=["en_progreso", "finalizado", "vencido"]),
    ],
    responses={200: s.ResultadoSerializer(many=True), 401: NO_AUTENTICADO},
)
class ResultadoListView(generics.ListAPIView):
    serializer_class = s.ResultadoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if puede_auditar_resultados(user):
            qs = consultas.alcance_de(user).intentos()
        else:
            qs = Intento.objects.filter(participante_codigo=codigo_participante(user))
        params = self.request.query_params
        if params.get("simulacro", "").isdigit():
            qs = qs.filter(cuestionario_id=params["simulacro"])
        if params.get("estado") in ("en_progreso", "finalizado", "vencido"):
            qs = qs.filter(estado=params["estado"])
        return qs.select_related("cuestionario", "curso__periodo", "periodo").order_by("-fecha_inicio", "-id")


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

@extend_schema(
    tags=["Reportes"],
    summary="Reporte filtrado por año, curso y eje temático",
    description=(
        "Los mismos cálculos del módulo de consultas: indicadores generales y resúmenes por "
        "período, curso y eje temático. Las notas se expresan sobre 5,0 y solo cuentan los "
        "intentos terminados.\n\n"
        "Requiere `resultados.consultar_todos`. Un docente solo ve sus cursos: pedir un curso o "
        "período ajeno responde 403. Un filtro incompatible con su filtro padre (p. ej. un curso "
        "de otro año) se quita y se informa en `avisos`."
    ),
    parameters=[
        OpenApiParameter("anio", OpenApiTypes.INT, description="Año académico, p. ej. 2026."),
        OpenApiParameter("periodo", OpenApiTypes.INT, description="Id del período académico."),
        OpenApiParameter("curso", OpenApiTypes.INT, description="Id del curso."),
        OpenApiParameter("eje", OpenApiTypes.INT, description="Id del eje temático (categoría de preguntas)."),
        OpenApiParameter("visibilidad", OpenApiTypes.STR, enum=["institucional", "privado"]),
        OpenApiParameter("estudiante", OpenApiTypes.STR, description="Código institucional del estudiante."),
    ],
    responses={200: s.ReporteSerializer, 401: NO_AUTENTICADO, 403: SIN_PERMISO},
)
class ReporteView(APIView):
    permission_classes = [requiere("resultados.consultar_todos")]

    def get(self, request):
        alcance = consultas.alcance_de(request.user)
        filtros = consultas.leer_filtros(request.query_params, alcance)
        qs = consultas.intentos_filtrados(filtros, alcance)
        datos = {
            "filtros": [{"filtro": n, "valor": v} for n, v in filtros.activos],
            "avisos": filtros.avisos,
            "indicadores": consultas.indicadores(qs),
            "por_periodo": consultas.por_periodo(qs),
            "por_curso": consultas.por_curso(qs),
            "por_eje": consultas.por_eje(qs, filtros),
        }
        return Response(s.ReporteSerializer(datos).data)
