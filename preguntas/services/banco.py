"""
Módulo A: reglas del banco de preguntas (alta, edición, deduplicación por
huella SHA-256 y borrado lógico). Las vistas solo traducen el formulario.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction

from preguntas.models import Categoria, OpcionRespuesta, Pregunta
from .importador_excel import calcular_huella

LETRAS_MULTIPLE = ("A", "B", "C", "D")


class PreguntaDuplicada(Exception):
    """Ya existe una pregunta con la misma huella de contenido."""


@dataclass
class DatosPregunta:
    categoria_id: int | None
    tipo: str
    enunciado: str
    texto_base: str | None = None
    retroalimentacion: str | None = None
    puntaje: Decimal = Decimal("1.00")
    # (texto, es_correcta, orden)
    opciones: list[tuple[str, bool, int]] = field(default_factory=list)


def _decimal(valor, por_defecto="1.00") -> Decimal:
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(por_defecto)


def datos_desde_formulario(post, tipo_por_defecto=Pregunta.TIPO_MULTIPLE) -> DatosPregunta:
    """Traduce el POST de los modales de crear/editar a `DatosPregunta`."""
    tipo = post.get("tipo", tipo_por_defecto)
    if tipo == Pregunta.TIPO_MULTIPLE:
        correcta = post.get("correcta", "A")
        opciones = [
            (post.get(f"opcion_{letra.lower()}", "").strip(), correcta == letra, orden)
            for orden, letra in enumerate(LETRAS_MULTIPLE, start=1)
        ]
    else:
        correcta_vf = post.get("correcta_vf", "V")
        opciones = [
            ("Verdadero", correcta_vf == "V", 1),
            ("Falso", correcta_vf == "F", 2),
        ]
    return DatosPregunta(
        categoria_id=post.get("categoria_id"),
        tipo=tipo,
        enunciado=post.get("enunciado", "").strip(),
        texto_base=post.get("texto_base", "").strip() or None,
        retroalimentacion=post.get("retroalimentacion", "").strip() or None,
        puntaje=_decimal(post.get("puntaje", "1.00")),
        opciones=opciones,
    )


@transaction.atomic
def guardar_pregunta(datos: DatosPregunta, pregunta: Pregunta | None = None) -> Pregunta:
    """Crea o actualiza una pregunta con sus opciones. Lanza `PreguntaDuplicada`."""
    huella = calcular_huella(datos.enunciado, [texto for texto, _, _ in datos.opciones])
    duplicadas = Pregunta.objects.filter(huella_contenido=huella)
    if pregunta:
        duplicadas = duplicadas.exclude(id=pregunta.id)
    if duplicadas.exists():
        raise PreguntaDuplicada()

    pregunta = pregunta or Pregunta(activa=True)
    pregunta.categoria = Categoria.objects.get(id=datos.categoria_id)
    pregunta.tipo = datos.tipo
    pregunta.texto_base = datos.texto_base
    pregunta.enunciado = datos.enunciado
    pregunta.retroalimentacion = datos.retroalimentacion
    pregunta.puntaje = datos.puntaje
    pregunta.huella_contenido = huella
    pregunta.save()

    pregunta.opciones.all().delete()
    OpcionRespuesta.objects.bulk_create([
        OpcionRespuesta(pregunta=pregunta, texto=texto, es_correcta=es_correcta, orden=orden)
        for texto, es_correcta, orden in datos.opciones
    ])
    return pregunta


def alternar_estado(pregunta: Pregunta) -> Pregunta:
    """Borrado lógico: activa o desactiva sin eliminar el registro."""
    pregunta.activa = not pregunta.activa
    pregunta.save(update_fields=["activa"])
    return pregunta


def serializar_para_edicion(pregunta: Pregunta) -> dict:
    return {
        "id": pregunta.id,
        "categoria_id": pregunta.categoria_id,
        "tipo": pregunta.tipo,
        "texto_base": pregunta.texto_base or "",
        "enunciado": pregunta.enunciado,
        "puntaje": str(pregunta.puntaje),
        "retroalimentacion": pregunta.retroalimentacion or "",
        "opciones": list(
            pregunta.opciones.order_by("orden", "id").values("id", "texto", "es_correcta", "orden")
        ),
    }
