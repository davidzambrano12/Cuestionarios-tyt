"""Consultas de la estructura académica usadas por otras apps."""
from django.utils import timezone

from apps.academico.models import Curso, Matricula


def curso_vigente(user, cuando=None) -> Curso | None:
    """Curso activo del estudiante cuyo período incluye la fecha `cuando`."""
    fecha = timezone.localdate(cuando) if cuando else timezone.localdate()
    matricula = (
        Matricula.objects.filter(
            estudiante=user,
            curso__activo=True,
            curso__periodo__fecha_inicio__lte=fecha,
            curso__periodo__fecha_fin__gte=fecha,
        )
        .select_related("curso")
        .order_by("-curso__periodo__fecha_inicio", "curso__nombre")
        .first()
    )
    return matricula.curso if matricula else None


def asignar_cursos_pendientes() -> int:
    """
    Asigna el curso a los intentos que aún no lo tienen, buscando al
    estudiante por su código institucional y su matrícula vigente en la
    fecha del intento. Retorna cuántos intentos se actualizaron.
    """
    from django.contrib.auth.models import User

    from apps.core.services.acceso import codigo_participante
    from apps.evaluaciones.models import Intento

    pendientes = Intento.objects.filter(curso__isnull=True)
    codigos = set(pendientes.values_list("participante_codigo", flat=True))
    if not codigos:
        return 0
    usuarios = {}
    for user in User.objects.filter(matriculas__isnull=False).select_related("perfil").distinct():
        usuarios[codigo_participante(user)] = user

    actualizados = 0
    for intento in pendientes.filter(participante_codigo__in=usuarios.keys()):
        curso = curso_vigente(usuarios[intento.participante_codigo], intento.fecha_inicio)
        if curso:
            Intento.objects.filter(id=intento.id).update(curso=curso)
            actualizados += 1
    return actualizados
