"""
Módulos D y E: ciclo de vida del intento (inicio, reanudación, control de
tiempo validado en servidor, autoguardado) y motor de calificación.

    calificacion = (puntaje_obtenido / puntaje_total_posible) * calificacion_maxima
"""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.cuestionarios import acceso
from apps.core.services.acceso import codigo_participante
from apps.banco_preguntas.models import OpcionRespuesta, Pregunta
from apps.cuestionarios.models import Cuestionario, CuestionarioPregunta
from apps.evaluaciones.models import Intento, RespuestaIntento

VENTANA_GRACIA_SEG = 30  # tolerancia de red al vencer el tiempo (RULE-04)
LETRAS = ["A", "B", "C", "D", "E"]


# ------------------------------------------------------------------------------
# Dictamen de un intento
# ------------------------------------------------------------------------------

ESTADOS_CERRADOS = ("finalizado", "vencido")


def intento_calificado(intento) -> bool:
    """Un intento cuenta para la nota solo si está cerrado y tiene calificación."""
    return intento.estado in ESTADOS_CERRADOS and intento.calificacion is not None


def dictamen_intento(intento, cuestionario) -> str:
    """Dictamen legible y coherente para pantallas y exportaciones."""
    if intento.estado == "en_progreso":
        return "En curso"
    if not intento_calificado(intento):
        return "Vencido sin calificar"
    return "Aprobado" if intento.calificacion >= cuestionario.calificacion_aprobacion else "Reprobado"


# ------------------------------------------------------------------------------
# Control de tiempo
# ------------------------------------------------------------------------------

def segundos_transcurridos(intento: Intento, ahora=None) -> int:
    ahora = ahora or timezone.now()
    return int((ahora - intento.fecha_inicio).total_seconds())


def excedio_tiempo(intento: Intento, ahora=None) -> bool:
    limite = intento.cuestionario.tiempo_limite_minutos * 60
    return segundos_transcurridos(intento, ahora) > limite + VENTANA_GRACIA_SEG


def segundos_restantes(intento: Intento, ahora=None) -> int:
    limite = intento.cuestionario.tiempo_limite_minutos * 60
    return max(1, limite - segundos_transcurridos(intento, ahora))


def cerrar_como_vencido(intento: Intento, ahora=None) -> Intento:
    ahora = ahora or timezone.now()
    intento.estado = "vencido"
    intento.fecha_fin = ahora
    intento.duracion_segundos = segundos_transcurridos(intento, ahora)
    intento.save(update_fields=["estado", "fecha_fin", "duracion_segundos"])
    return intento


def cerrar_si_vencio(intento: Intento, ahora=None) -> bool:
    """Cierra el intento en curso si superó el tiempo. Retorna True si lo cerró."""
    if intento.estado == "en_progreso" and excedio_tiempo(intento, ahora):
        cerrar_como_vencido(intento, ahora)
        return True
    return False


# ------------------------------------------------------------------------------
# Inicio y reanudación
# ------------------------------------------------------------------------------

@dataclass
class ResultadoInicio:
    """Desenlace de `iniciar_intento`. `tipo` guía la redirección de la vista."""
    tipo: str  # "nuevo" | "reanudado" | "vencido" | "rechazado" | "elegir_curso"
    intento: Intento | None = None
    mensaje: str = ""
    cursos: list = None  # cuando tipo == "elegir_curso"


def iniciar_intento(user, cuestionario: Cuestionario, ahora=None, curso_id=None) -> ResultadoInicio:
    """Valida disponibilidad, fechas e intentos (RF/R08) y crea o reanuda el intento."""
    ahora = ahora or timezone.now()

    if not user.is_active:
        return ResultadoInicio("rechazado", mensaje="Su cuenta se encuentra suspendida.")
    if cuestionario.estado != "disponible":
        return ResultadoInicio("rechazado", mensaje="Esta evaluación no se encuentra disponible actualmente.")
    if ahora < cuestionario.fecha_apertura:
        return ResultadoInicio(
            "rechazado", mensaje=f"La evaluación aún no ha iniciado. Abre el {cuestionario.fecha_apertura}.",
        )
    if ahora > cuestionario.fecha_cierre:
        return ResultadoInicio("rechazado", mensaje="El plazo para presentar este cuestionario ha expirado.")
    cursos = acceso.cursos_para_presentar(user, cuestionario, ahora)
    if not cuestionario.es_institucional and not cursos:
        return ResultadoInicio(
            "rechazado", mensaje="Este cuestionario es de un curso en el que no estás matriculado este período.",
        )

    codigo = codigo_participante(user)
    activos = list(
        Intento.objects.filter(cuestionario=cuestionario, participante_codigo=codigo, estado="en_progreso")
        .select_related("cuestionario")
        .order_by("-fecha_inicio")
    )
    if activos:
        actual, *huerfanos = activos
        for extra in huerfanos:  # no debería haber más de uno abierto
            cerrar_como_vencido(extra, ahora)
        if cerrar_si_vencio(actual, ahora):
            return ResultadoInicio(
                "vencido", actual, "Tu intento previo expiró por límite de tiempo y ha sido cerrado.",
            )
        return ResultadoInicio(
            "reanudado", actual, "Reanudando tu intento en curso. El tiempo continúa corriendo en el servidor.",
        )

    usados = Intento.objects.filter(
        cuestionario=cuestionario, participante_codigo=codigo, estado__in=["finalizado", "vencido"],
    ).count()
    if usados >= cuestionario.intentos_permitidos:
        return ResultadoInicio(
            "rechazado",
            mensaje=f"Has alcanzado el límite máximo de {cuestionario.intentos_permitidos} intentos permitidos para este cuestionario.",
        )

    # Curso al que cuenta el intento: si hay varios posibles, elige el estudiante
    curso = cursos[0] if len(cursos) == 1 else None
    if len(cursos) > 1:
        curso = next((c for c in cursos if str(c.id) == str(curso_id)), None)
        if curso is None:
            return ResultadoInicio("elegir_curso", cursos=cursos)

    intento = Intento.objects.create(
        cuestionario=cuestionario,
        curso=curso,
        periodo=curso.periodo if curso else acceso.periodo_vigente(ahora),
        participante_nombre=user.get_full_name() or user.username,
        participante_codigo=codigo,
        estado="en_progreso",
    )
    return ResultadoInicio("nuevo", intento)


# ------------------------------------------------------------------------------
# Respuestas y calificación
# ------------------------------------------------------------------------------

def _peso(cp: CuestionarioPregunta | None, pregunta: Pregunta) -> Decimal:
    if cp and cp.puntaje_asignado:
        return cp.puntaje_asignado
    return pregunta.puntaje or Decimal("1.00")


def guardar_respuesta(intento: Intento, pregunta_id: int, opcion_id=None, marcada: bool = False) -> RespuestaIntento:
    """Autoguardado asíncrono de una selección (o de su borrado si `opcion_id` es None)."""
    pregunta = Pregunta.objects.get(id=pregunta_id)
    opcion = None
    if opcion_id:
        opcion = OpcionRespuesta.objects.filter(id=int(opcion_id), pregunta=pregunta).first()
    es_correcta = bool(opcion and opcion.es_correcta)
    cp = CuestionarioPregunta.objects.filter(cuestionario=intento.cuestionario, pregunta=pregunta).first()

    respuesta, _ = RespuestaIntento.objects.update_or_create(
        intento=intento,
        pregunta=pregunta,
        defaults={
            "opcion_seleccionada": opcion,
            "es_correcta": es_correcta,
            "puntaje_obtenido": _peso(cp, pregunta) if es_correcta else Decimal("0.00"),
            "marcada_para_revision": marcada,
        },
    )
    return respuesta


def calcular_calificacion(puntaje_obtenido: Decimal, puntaje_total: Decimal, maxima: Decimal) -> Decimal:
    if puntaje_total <= 0:
        return Decimal("0.00")
    return round((puntaje_obtenido / puntaje_total) * maxima, 2)


@transaction.atomic
def calificar_intento(intento: Intento, respuestas: dict, ahora=None) -> Intento:
    """
    Registra todas las respuestas (las omitidas con opción NULL, R09), aplica la
    fórmula institucional y cierra el intento como `finalizado`.
    `respuestas` es {pregunta_id: opcion_id} con claves str o int.
    """
    ahora = ahora or timezone.now()
    cuestionario = intento.cuestionario
    asignaciones = cuestionario.cuestionario_preguntas.select_related("pregunta").order_by("orden", "id")

    opciones_elegidas = {}
    for cp in asignaciones:
        opcion_id = respuestas.get(str(cp.pregunta_id)) or respuestas.get(cp.pregunta_id)
        if opcion_id:
            opciones_elegidas[cp.pregunta_id] = int(opcion_id)
    opciones = {
        op.id: op
        for op in OpcionRespuesta.objects.filter(id__in=opciones_elegidas.values())
    }

    intento.respuestas.all().delete()
    puntaje_obtenido = Decimal("0.00")
    puntaje_total = Decimal("0.00")
    nuevas = []
    for cp in asignaciones:
        peso = _peso(cp, cp.pregunta)
        puntaje_total += peso
        opcion = opciones.get(opciones_elegidas.get(cp.pregunta_id))
        if opcion and opcion.pregunta_id != cp.pregunta_id:
            opcion = None  # una opción de otra pregunta no cuenta
        es_correcta = bool(opcion and opcion.es_correcta)
        if es_correcta:
            puntaje_obtenido += peso
        nuevas.append(RespuestaIntento(
            intento=intento,
            pregunta=cp.pregunta,
            opcion_seleccionada=opcion,
            es_correcta=es_correcta,
            puntaje_obtenido=peso if es_correcta else Decimal("0.00"),
        ))
    RespuestaIntento.objects.bulk_create(nuevas)

    calificacion = calcular_calificacion(puntaje_obtenido, puntaje_total, cuestionario.calificacion_maxima)
    intento.fecha_fin = ahora
    intento.duracion_segundos = max(segundos_transcurridos(intento, ahora), 1)
    intento.puntaje_obtenido = puntaje_obtenido
    intento.puntaje_total_posible = puntaje_total
    intento.calificacion = calificacion
    intento.aprobado = calificacion >= cuestionario.calificacion_aprobacion
    intento.estado = "finalizado"
    intento.save()

    # Cerrar cualquier otro intento huérfano que siguiera abierto
    Intento.objects.filter(
        cuestionario=cuestionario, participante_codigo=intento.participante_codigo, estado="en_progreso",
    ).exclude(id=intento.id).update(estado="vencido", fecha_fin=ahora, duracion_segundos=1)
    return intento


# ------------------------------------------------------------------------------
# Revisión pedagógica (RF-24)
# ------------------------------------------------------------------------------

def revision_intento(intento: Intento, *, detallada: bool) -> dict:
    """
    Totales de aciertos y, si `detallada`, el desglose por pregunta con la
    opción marcada, la correcta y la retroalimentación.
    """
    respuestas = list(
        intento.respuestas
        .select_related("pregunta", "pregunta__categoria", "opcion_seleccionada")
        .prefetch_related("pregunta__opciones")
    )
    correctas = sum(1 for r in respuestas if r.es_correcta)
    sin_responder = sum(1 for r in respuestas if r.opcion_seleccionada_id is None)
    incorrectas = len(respuestas) - correctas - sin_responder

    detalles = []
    if detallada:
        orden = {
            cp.pregunta_id: (cp.orden, cp.puntaje_asignado)
            for cp in intento.cuestionario.cuestionario_preguntas.all()
        }
        respuestas.sort(key=lambda r: orden.get(r.pregunta_id, (9999, None))[0])
        for numero, resp in enumerate(respuestas, start=1):
            pregunta = resp.pregunta
            opciones = sorted(pregunta.opciones.all(), key=lambda o: (o.orden, o.id))
            if resp.opcion_seleccionada_id is None:
                estado = "sin_responder"
            elif resp.es_correcta:
                estado = "correcta"
            else:
                estado = "incorrecta"
            detalles.append({
                "numero": numero,
                "pregunta": pregunta,
                "peso_total": orden.get(pregunta.id, (numero, None))[1] or pregunta.puntaje or Decimal("1.00"),
                "puntaje_obtenido": resp.puntaje_obtenido or Decimal("0.00"),
                "estado": estado,
                "es_correcta": resp.es_correcta,
                "opcion_seleccionada": resp.opcion_seleccionada,
                "opcion_correcta": next((op for op in opciones if op.es_correcta), None),
                "opciones": [
                    {
                        "letra": LETRAS[i] if i < len(LETRAS) else str(i + 1),
                        "id": op.id,
                        "texto": op.texto,
                        "es_correcta": op.es_correcta,
                        "es_seleccionada": resp.opcion_seleccionada_id == op.id,
                    }
                    for i, op in enumerate(opciones)
                ],
                "retroalimentacion": pregunta.retroalimentacion,
            })

    total = len(respuestas)
    return {
        "detalles_respuestas": detalles,
        "total_preguntas": total,
        "total_correctas": correctas,
        "total_incorrectas": incorrectas,
        "total_sin_responder": sin_responder,
        "porcentaje_acierto": round(correctas / total * 100, 1) if total else 0,
    }


# ------------------------------------------------------------------------------
# Panel del estudiante
# ------------------------------------------------------------------------------

def _anotar_intentos(cuestionario, activos: dict, hechos: dict) -> None:
    cuestionario.intento_activo = activos.get(cuestionario.id)
    cuestionario.intentos_hechos = hechos.get(cuestionario.id, 0)
    cuestionario.intentos_restantes = max(0, cuestionario.intentos_permitidos - cuestionario.intentos_hechos)
    cuestionario.intentos_agotados = (
        cuestionario.intentos_hechos >= cuestionario.intentos_permitidos and not cuestionario.intento_activo
    )
    cuestionario.siguiente_intento_num = min(cuestionario.intentos_permitidos, cuestionario.intentos_hechos + 1)


def panel_estudiante(user, ahora=None) -> dict:
    """Cuestionarios vigentes y programados con el estado de intentos del estudiante."""
    ahora = ahora or timezone.now()
    codigo = codigo_participante(user)

    visibles = acceso.visibles_para_estudiante(user, ahora)
    disponibles = list(
        visibles.filter(estado="disponible", fecha_apertura__lte=ahora, fecha_cierre__gte=ahora)
        .prefetch_related("cuestionario_preguntas", "intentos")
        .order_by("fecha_cierre")
    )
    programados = list(
        visibles.filter(Q(estado="programado") | Q(estado="disponible", fecha_apertura__gt=ahora))
        .prefetch_related("cuestionario_preguntas")
        .order_by("fecha_apertura")
    )

    # Intentos abiertos: se cierran los vencidos y los duplicados huérfanos
    activos = {}
    en_curso = (
        Intento.objects.filter(participante_codigo=codigo, estado="en_progreso")
        .select_related("cuestionario")
        .order_by("-fecha_inicio")
    )
    for intento in en_curso:
        if cerrar_si_vencio(intento, ahora):
            continue
        if intento.cuestionario_id in activos:
            cerrar_como_vencido(intento, ahora)
        else:
            activos[intento.cuestionario_id] = intento

    hechos = {
        fila["cuestionario_id"]: fila["total"]
        for fila in Intento.objects.filter(participante_codigo=codigo, estado__in=["finalizado", "vencido"])
        .values("cuestionario_id")
        .annotate(total=Count("id"))
    }
    for cuestionario in disponibles:
        _anotar_intentos(cuestionario, activos, hechos)

    historial = list(
        Intento.objects.filter(participante_codigo=codigo).select_related("cuestionario").order_by("-fecha_inicio")
    )
    for intento in historial:
        intento.dictamen = dictamen_intento(intento, intento.cuestionario)
    calificados = [i.calificacion for i in historial if intento_calificado(i)]
    promedio = sum(calificados) / len(calificados) if calificados else None

    return {
        "cuestionarios_disponibles": disponibles,
        "cuestionarios_programados": programados,
        "cuestionario_destacado": disponibles[0] if disponibles else None,
        "intentos_estudiante": historial,
        "presentados_count": sum(1 for i in historial if i.estado != "en_progreso"),
        "disponibles_count": len(disponibles),
        "programados_count": len(programados),
        # Decimal para que la plantilla lo formatee según el idioma (5,00)
        "promedio_global": Decimal(promedio).quantize(Decimal("0.01")) if promedio is not None else Decimal("0.00"),
    }
