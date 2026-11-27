"""
Ciclo de vida del cuestionario (RF-15): acciones del docente sobre su estado.

    borrador ──publicar──▶ publicado ──ocultar──▶ oculto ──mostrar──▶ publicado
                              │  ▲                  │
                         cerrar  reabrir         cerrar
                              ▼  │                  ▼
                            cerrado ◀───────────────┘
                              │  ▲
                        archivar  desarchivar
                              ▼  │
                            archivado ◀──archivar── borrador

"Programado" no es una acción: es un cuestionario publicado cuya apertura no
ha llegado. Un publicado cuya fecha de cierre ya pasó se comporta como cerrado.

Ocultar o cerrar impide iniciar intentos nuevos, pero quien ya está
presentando puede terminar: el tiempo se sigue validando en el servidor.
"""
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.cuestionarios.models import Cuestionario

C = Cuestionario


@dataclass(frozen=True)
class Accion:
    codigo: str
    etiqueta: str
    icono: str
    destino: str
    exito: str
    # Confirmación antes de aplicar (vacía = no se pide)
    confirmar: str = ""
    tipo_confirmacion: str = "aviso"


ACCIONES = {
    "publicar": Accion(
        "publicar", "Publicar", "send", C.PUBLICADO, "publicado",
        "Los estudiantes podrán verlo y presentarlo dentro de las fechas configuradas.", "primario",
    ),
    "ocultar": Accion(
        "ocultar", "Ocultar", "eye-off", C.OCULTO, "ocultado",
        "Los estudiantes dejarán de verlo y no podrán iniciar intentos. Quien ya esté "
        "presentando puede terminar. Podrás volver a mostrarlo cuando quieras.",
    ),
    "mostrar": Accion("mostrar", "Mostrar", "eye", C.PUBLICADO, "visible de nuevo"),
    "cerrar": Accion(
        "cerrar", "Cerrar ahora", "lock", C.CERRADO, "cerrado",
        "Nadie podrá iniciar intentos nuevos aunque la fecha de cierre no haya llegado. "
        "Quien ya esté presentando puede terminar.", "peligro",
    ),
    "reabrir": Accion("reabrir", "Reabrir", "lock-open", C.PUBLICADO, "reabierto"),
    "archivar": Accion(
        "archivar", "Archivar", "archive", C.ARCHIVADO, "archivado",
        "Saldrá de las listas de estudiantes y docentes. Sus resultados se conservan "
        "en los reportes y puedes desarchivarlo después.",
    ),
    "desarchivar": Accion("desarchivar", "Desarchivar", "archive-restore", C.CERRADO, "desarchivado"),
}


class CambioNoPermitido(Exception):
    """La acción no aplica al estado actual o el cuestionario no cumple sus requisitos."""


def acciones_disponibles(cuestionario: Cuestionario, ahora=None) -> list[Accion]:
    """Acciones que tienen sentido desde el estado actual, en orden de uso."""
    ahora = ahora or timezone.now()
    vencido_por_fecha = bool(cuestionario.fecha_cierre and ahora > cuestionario.fecha_cierre)
    estado = cuestionario.estado
    codigos = []
    if estado == C.BORRADOR:
        codigos = ["publicar", "archivar"]
    elif estado == C.PUBLICADO:
        codigos = ["archivar"] if vencido_por_fecha else ["ocultar", "cerrar"]
    elif estado == C.OCULTO:
        codigos = ["mostrar", "cerrar"]
    elif estado == C.CERRADO:
        codigos = ["archivar"] if vencido_por_fecha else ["reabrir", "archivar"]
    elif estado == C.ARCHIVADO:
        codigos = ["desarchivar"]
    return [ACCIONES[c] for c in codigos]


def problemas_para_publicar(cuestionario: Cuestionario) -> list[str]:
    """Las mismas reglas que exige el editor al pulsar «Publicar»."""
    problemas = []
    preguntas = cuestionario.cuestionario_preguntas.select_related("pregunta")
    if not preguntas.exists():
        problemas.append("No se puede publicar un cuestionario sin preguntas.")
    elif preguntas.filter(pregunta__activa=False).exists():
        problemas.append("Retira las preguntas inactivas antes de publicarlo.")
    if not cuestionario.es_institucional and not cuestionario.cursos.exists():
        problemas.append("Para publicar un cuestionario de curso, asígnalo al menos a un curso.")
    return problemas


@transaction.atomic
def aplicar_accion(cuestionario: Cuestionario, codigo: str, ahora=None) -> Accion:
    """Cambia el estado si la acción está permitida; si no, lanza CambioNoPermitido."""
    ahora = ahora or timezone.now()
    accion = ACCIONES.get(codigo)
    if accion is None:
        raise CambioNoPermitido("Acción desconocida.")
    # Se bloquea la fila para que dos clics simultáneos no dejen estados cruzados
    cuestionario = Cuestionario.objects.select_for_update().get(pk=cuestionario.pk)
    if accion not in acciones_disponibles(cuestionario, ahora):
        if codigo == "reabrir" and cuestionario.estado == C.CERRADO:
            raise CambioNoPermitido(
                "La fecha de cierre ya pasó. Amplíala en «Configurar» para poder reabrirlo."
            )
        raise CambioNoPermitido(
            f"No se puede {accion.etiqueta.lower()} un cuestionario en estado "
            f"«{cuestionario.get_estado_display()}»."
        )
    if accion.destino == C.PUBLICADO:
        problemas = problemas_para_publicar(cuestionario)
        if problemas:
            raise CambioNoPermitido(" ".join(problemas))
    cuestionario.estado = accion.destino
    cuestionario.save(update_fields=["estado"])
    return accion
