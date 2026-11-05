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
        .order_by("-curso__periodo__fecha_inicio", "curso__asignatura", "curso__grupo")
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


# ---------------------------------------------------------------------------
# Gestión de cursos y matrículas
# ---------------------------------------------------------------------------

def es_admin(user) -> bool:
    from apps.core.services.acceso import perfil_de

    perfil = perfil_de(user)
    return bool(user.is_superuser or (perfil and perfil.es_admin))


def cursos_visibles(user):
    """Administrador: todos los cursos. Docente: solo los que tiene a cargo."""
    cursos = Curso.objects.select_related("periodo", "docente")
    return cursos if es_admin(user) else cursos.filter(docente=user)


def puede_gestionar(user, curso: Curso) -> bool:
    return es_admin(user) or curso.docente_id == user.id


def estudiantes_elegibles():
    """Cuentas activas con rol de estudiante."""
    from django.contrib.auth.models import User

    return (
        User.objects.filter(is_active=True, perfil__rol__codigo="estudiante")
        .select_related("perfil")
        .order_by("first_name", "last_name", "username")
    )


def _intentos_sin_curso(user, periodo):
    from apps.core.services.acceso import codigo_participante
    from apps.evaluaciones.models import Intento

    return Intento.objects.filter(
        curso__isnull=True,
        participante_codigo=codigo_participante(user),
        fecha_inicio__range=rango_del_periodo(periodo),
    )


def rango_del_periodo(periodo):
    """Del inicio del primer día al final del último, en la zona local.
    (Se evita `__date`: en MariaDB depende de las tablas de zonas horarias.)"""
    from datetime import datetime, time, timedelta

    inicio = timezone.make_aware(datetime.combine(periodo.fecha_inicio, time.min))
    fin = timezone.make_aware(datetime.combine(periodo.fecha_fin + timedelta(days=1), time.min)) - timedelta(microseconds=1)
    return inicio, fin


def matricular(curso: Curso, estudiantes) -> dict:
    """
    Matricula a los estudiantes indicados en el curso. Los intentos que ya
    habían presentado en ese período sin curso quedan asociados a él.
    """
    nuevos, ya_estaban, en_otro_curso, asignados = [], [], [], 0
    for est in estudiantes:
        _, creada = Matricula.objects.get_or_create(curso=curso, estudiante=est)
        if not creada:
            ya_estaban.append(est)
            continue
        nuevos.append(est)
        if Matricula.objects.filter(estudiante=est, curso__periodo=curso.periodo).exclude(curso=curso).exists():
            en_otro_curso.append(est)
        asignados += _intentos_sin_curso(est, curso.periodo).update(curso=curso)
    return {"nuevos": nuevos, "ya_estaban": ya_estaban, "en_otro_curso": en_otro_curso,
            "intentos_asignados": asignados}


class RetiroNoPermitido(Exception):
    pass


def retirar(matricula: Matricula) -> None:
    """Retira al estudiante del curso, salvo que ya tenga intentos en él (se conserva el historial)."""
    from apps.core.services.acceso import codigo_participante
    from apps.evaluaciones.models import Intento

    codigo = codigo_participante(matricula.estudiante)
    intentos = Intento.objects.filter(curso=matricula.curso, participante_codigo=codigo).count()
    if intentos:
        raise RetiroNoPermitido(
            f"No se puede retirar: tiene {intentos} intento{'s' if intentos != 1 else ''} en este curso "
            "y su historial debe conservarse. Puedes desactivar el curso al terminar el período."
        )
    matricula.delete()


def resumen_sin_curso() -> dict:
    """Intentos terminados que no tienen curso (para avisar al administrador)."""
    from apps.evaluaciones.models import Intento

    pendientes = Intento.objects.filter(curso__isnull=True, estado__in=("finalizado", "vencido"))
    return {
        "intentos": pendientes.count(),
        "estudiantes": pendientes.values("participante_codigo").distinct().count(),
    }
