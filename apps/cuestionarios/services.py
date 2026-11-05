"""
Módulo C: configuración de cuestionarios y armado del examen (orden,
barajado determinista y serialización para la sala o la previsualización).
"""
import random
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.banco_preguntas.models import Pregunta
from apps.cuestionarios.models import Cuestionario, CuestionarioPregunta

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
    fecha_apertura: object
    fecha_cierre: object
    tiempo_limite_minutos: int
    intentos_permitidos: int
    calificacion_maxima: Decimal
    calificacion_aprobacion: Decimal
    mezclar_preguntas: bool
    mezclar_respuestas: bool
    permitir_revision: bool
    estado: str
    preguntas_ids: list = field(default_factory=list)


class DatosInvalidos(Exception):
    """El formulario no cumple las reglas R01-R04 del cuestionario."""

    def __init__(self, errores, datos=None):
        super().__init__("; ".join(errores))
        self.errores = errores
        self.datos = datos


def _fecha(valor):
    fecha = parse_datetime(valor or "")
    if fecha and timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha)
    return fecha


def datos_desde_formulario(post) -> DatosCuestionario:
    """Traduce el POST del editor y valida las reglas de la tabla cuestionarios."""
    errores = []

    def numero(campo, tipo, por_defecto, etiqueta):
        try:
            return tipo(post.get(campo) or por_defecto)
        except (ValueError, InvalidOperation):
            errores.append(f"{etiqueta} debe ser un número.")
            return tipo(por_defecto)

    datos = DatosCuestionario(
        nombre=post.get("nombre", "").strip(),
        descripcion=post.get("descripcion", "").strip(),
        fecha_apertura=_fecha(post.get("fecha_apertura")),
        fecha_cierre=_fecha(post.get("fecha_cierre")),
        tiempo_limite_minutos=numero("tiempo_limite_minutos", int, 120, "El tiempo límite"),
        intentos_permitidos=numero("intentos_permitidos", int, 5, "Los intentos permitidos"),
        calificacion_maxima=numero("calificacion_maxima", Decimal, "5.00", "La calificación máxima"),
        calificacion_aprobacion=numero("calificacion_aprobacion", Decimal, "3.00", "La nota de aprobación"),
        mezclar_preguntas=bool(post.get("mezclar_preguntas")),
        mezclar_respuestas=bool(post.get("mezclar_respuestas")),
        permitir_revision=bool(post.get("permitir_revision")),
        estado="disponible" if post.get("accion") == "publicar" else "borrador",
        preguntas_ids=post.getlist("preguntas_ids"),
    )

    # Reglas R01-R04: las mismas CHECK de la tabla cuestionarios en MariaDB
    if not datos.nombre:
        errores.append("El nombre del cuestionario es obligatorio.")
    if not datos.fecha_apertura or not datos.fecha_cierre:
        errores.append("Las fechas de apertura y cierre son obligatorias.")
    elif datos.fecha_cierre <= datos.fecha_apertura:
        errores.append("La fecha de cierre debe ser posterior a la de apertura.")
    if datos.calificacion_maxima <= 0:
        errores.append("La calificación máxima debe ser mayor que cero.")
    elif not (0 <= datos.calificacion_aprobacion <= datos.calificacion_maxima):
        errores.append("La nota de aprobación debe estar entre 0 y la calificación máxima.")
    if datos.tiempo_limite_minutos <= 0:
        errores.append("El tiempo límite debe ser mayor que cero.")
    if datos.intentos_permitidos <= 0:
        errores.append("Debe permitirse al menos un intento.")
    if datos.estado == "disponible" and not datos.preguntas_ids:
        errores.append("No se puede publicar un cuestionario sin preguntas.")

    if errores:
        raise DatosInvalidos(errores, datos)
    return datos


def cuestionario_sin_guardar(datos, original=None) -> Cuestionario:
    """Instancia con lo que escribió el docente, para volver a mostrar el formulario."""
    cuestionario = Cuestionario(id=original.id if original else None)
    for campo in CAMPOS_CONFIGURABLES:
        setattr(cuestionario, campo, getattr(datos, campo))
    cuestionario.estado = original.estado if original else "borrador"
    return cuestionario


def preguntas_por_ids(ids):
    """(asignaciones sin guardar, puntaje total) en el orden recibido."""
    ids = [int(i) for i in ids if str(i).isdigit()]
    preguntas = Pregunta.objects.select_related("categoria").in_bulk(ids)
    asignadas = [
        CuestionarioPregunta(pregunta=preguntas[i], puntaje_asignado=preguntas[i].puntaje, orden=n)
        for n, i in enumerate(ids, start=1) if i in preguntas
    ]
    return asignadas, sum((cp.puntaje_asignado for cp in asignadas), Decimal("0.00"))


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
        "disponibles_count": sum(1 for c in cuestionarios if c.estado_temporal == "disponible"),
        "borradores_count": sum(1 for c in cuestionarios if c.estado_temporal == "borrador"),
        "cerrados_count": sum(1 for c in cuestionarios if c.estado_temporal == "cerrado"),
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
