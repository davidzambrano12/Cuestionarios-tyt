"""
Módulo C: configuración de cuestionarios y armado del examen (orden,
barajado determinista y serialización para la sala o la previsualización).
"""
import random
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from preguntas.models import Cuestionario, CuestionarioPregunta, Pregunta

CAMPOS_CONFIGURABLES = (
    "nombre", "descripcion", "fecha_apertura", "fecha_cierre",
    "tiempo_limite_minutos", "intentos_permitidos",
    "calificacion_maxima", "calificacion_aprobacion",
    "mezclar_preguntas", "mezclar_respuestas", "permitir_revision", "estado",
)


@dataclass
class DatosCuestionario:
    nombre: str
    descripcion: str
    fecha_apertura: str
    fecha_cierre: str
    tiempo_limite_minutos: int
    intentos_permitidos: int
    calificacion_maxima: Decimal
    calificacion_aprobacion: Decimal
    mezclar_preguntas: bool
    mezclar_respuestas: bool
    permitir_revision: bool
    estado: str
    preguntas_ids: list = field(default_factory=list)


def datos_desde_formulario(post) -> DatosCuestionario:
    return DatosCuestionario(
        nombre=post.get("nombre", "").strip(),
        descripcion=post.get("descripcion", "").strip(),
        fecha_apertura=post.get("fecha_apertura"),
        fecha_cierre=post.get("fecha_cierre"),
        tiempo_limite_minutos=int(post.get("tiempo_limite_minutos", 120)),
        intentos_permitidos=int(post.get("intentos_permitidos", 5)),
        calificacion_maxima=Decimal(post.get("calificacion_maxima", "5.00")),
        calificacion_aprobacion=Decimal(post.get("calificacion_aprobacion", "3.00")),
        mezclar_preguntas=bool(post.get("mezclar_preguntas")),
        mezclar_respuestas=bool(post.get("mezclar_respuestas")),
        permitir_revision=bool(post.get("permitir_revision")),
        estado="disponible" if post.get("accion") == "publicar" else "borrador",
        preguntas_ids=post.getlist("preguntas_ids"),
    )


@transaction.atomic
def guardar_cuestionario(datos: DatosCuestionario, cuestionario: Cuestionario | None = None) -> Cuestionario:
    """Crea o actualiza el cuestionario y sincroniza sus preguntas (N:M) en orden."""
    cuestionario = cuestionario or Cuestionario()
    for campo in CAMPOS_CONFIGURABLES:
        setattr(cuestionario, campo, getattr(datos, campo))
    cuestionario.save()

    preguntas = Pregunta.objects.in_bulk(datos.preguntas_ids)
    CuestionarioPregunta.objects.filter(cuestionario=cuestionario).delete()
    CuestionarioPregunta.objects.bulk_create([
        CuestionarioPregunta(
            cuestionario=cuestionario,
            pregunta=preguntas[int(p_id)],
            orden=orden,
            puntaje_asignado=preguntas[int(p_id)].puntaje,
        )
        for orden, p_id in enumerate(datos.preguntas_ids, start=1)
    ])
    return cuestionario


def preguntas_asignadas(cuestionario: Cuestionario | None):
    """(asignaciones ordenadas, puntaje total) para el editor del cuestionario."""
    if not cuestionario:
        return [], Decimal("0.00")
    asignadas = list(
        cuestionario.cuestionario_preguntas
        .select_related("pregunta", "pregunta__categoria")
        .order_by("orden")
    )
    total = sum(
        (cp.puntaje_asignado or cp.pregunta.puntaje or Decimal("1.00") for cp in asignadas),
        Decimal("0.00"),
    )
    return asignadas, total


def resumen_listado(cuestionarios) -> dict:
    return {
        "total_count": len(cuestionarios),
        "disponibles_count": sum(1 for c in cuestionarios if c.esta_vigente),
        "borradores_count": sum(1 for c in cuestionarios if c.estado == "borrador"),
        "cerrados_count": sum(1 for c in cuestionarios if c.esta_vencido),
    }


def serializar_preguntas(cuestionario: Cuestionario, semilla: int, *, incluir_claves: bool) -> list[dict]:
    """
    Preguntas del cuestionario listas para la interfaz JS.

    `semilla` hace el barajado determinista (el mismo intento ve siempre el
    mismo orden tras recargar). `incluir_claves` solo debe usarse en la
    previsualización docente: expone la opción correcta y la retroalimentación.
    """
    asignaciones = (
        cuestionario.cuestionario_preguntas
        .select_related("pregunta", "pregunta__categoria")
        .prefetch_related("pregunta__opciones")
        .order_by("orden", "id")
    )
    preguntas = []
    for cp in asignaciones:
        p = cp.pregunta
        opciones = [
            {"id": op.id, "texto": op.texto, **({"es_correcta": op.es_correcta} if incluir_claves else {})}
            for op in sorted(p.opciones.all(), key=lambda o: (o.orden, o.id))
        ]
        if cuestionario.mezclar_respuestas:
            random.Random(semilla * 1000 + p.id).shuffle(opciones)

        item = {
            "id": p.id,
            "categoria": p.categoria.nombre if p.categoria else "General",
            "tipo": p.tipo,
            "texto_base": p.texto_base or "",
            "enunciado": p.enunciado,
            "puntaje": str(cp.puntaje_asignado or p.puntaje),
            "opciones": opciones,
        }
        if incluir_claves:
            item["retroalimentacion"] = p.retroalimentacion or ""
        preguntas.append(item)

    if cuestionario.mezclar_preguntas:
        random.Random(semilla).shuffle(preguntas)
    return preguntas
