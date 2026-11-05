"""
Quién edita, quién ve y quién presenta cada cuestionario.

  * Institucional: cualquier estudiante activo puede presentarlo. Solo lo crean
    y editan los administradores o quien tenga `cuestionarios.publicar`.
  * De curso (privado): solo los estudiantes matriculados en los cursos
    asignados, en un curso activo del período vigente. Lo edita su creador
    (o un administrador), y solo puede asignarlo a cursos que gestiona.

El curso al que se atribuye un intento sale de `cursos_para_presentar`:
  * uno solo → ese curso;
  * varios → el estudiante elige al iniciar;
  * ninguno → privado: no puede presentarlo; institucional: queda sin curso
    (pero con su período, así cuenta en los reportes por año y período).
"""
from django.db.models import Q
from django.utils import timezone

from apps.academico.models import Curso, PeriodoAcademico
from apps.academico.services import cursos_visibles, es_admin
from apps.core.services.acceso import tiene_permiso
from apps.cuestionarios.models import Cuestionario


def puede_publicar_institucional(user) -> bool:
    return es_admin(user) or tiene_permiso(user, "cuestionarios.publicar")


def puede_editar(user, cuestionario: Cuestionario) -> bool:
    if es_admin(user):
        return True
    if cuestionario.es_institucional:
        return tiene_permiso(user, "cuestionarios.publicar")
    return cuestionario.creado_por_id == user.id


def editables(user):
    """Cuestionarios que el usuario puede editar, ver en reportes y gestionar."""
    qs = Cuestionario.objects.all()
    if es_admin(user):
        return qs
    condicion = Q(visibilidad=Cuestionario.PRIVADO, creado_por=user)
    if tiene_permiso(user, "cuestionarios.publicar"):
        condicion |= Q(visibilidad=Cuestionario.INSTITUCIONAL)
    return qs.filter(condicion)


def visibles_para_docente(user):
    """Los que puede editar más los institucionales (para previsualizarlos)."""
    if es_admin(user):
        return Cuestionario.objects.all()
    return Cuestionario.objects.filter(
        Q(id__in=editables(user).values("id")) | Q(visibilidad=Cuestionario.INSTITUCIONAL)
    )


def puede_ver_como_docente(user, cuestionario: Cuestionario) -> bool:
    return es_admin(user) or cuestionario.es_institucional or puede_editar(user, cuestionario)


def cursos_asignables(user):
    """Cursos activos a los que el usuario puede asignar un cuestionario de curso."""
    return cursos_visibles(user).filter(activo=True).order_by("-periodo__anio", "-periodo__numero", "asignatura", "grupo")


# ---------------------------------------------------------------------------
# Estudiantes
# ---------------------------------------------------------------------------

def _hoy(cuando=None):
    return timezone.localdate(cuando) if cuando else timezone.localdate()


def cursos_vigentes_del_estudiante(user, cuando=None):
    fecha = _hoy(cuando)
    return Curso.objects.filter(
        matriculas__estudiante=user, activo=True,
        periodo__fecha_inicio__lte=fecha, periodo__fecha_fin__gte=fecha,
    ).select_related("periodo").order_by("asignatura", "grupo")


def periodo_vigente(cuando=None) -> PeriodoAcademico | None:
    fecha = _hoy(cuando)
    return (
        PeriodoAcademico.objects.filter(fecha_inicio__lte=fecha, fecha_fin__gte=fecha)
        .order_by("-fecha_inicio").first()
    )


def visibles_para_estudiante(user, cuando=None):
    """Institucionales más los de curso asignados a sus cursos vigentes."""
    cursos = cursos_vigentes_del_estudiante(user, cuando)
    return Cuestionario.objects.filter(
        Q(visibilidad=Cuestionario.INSTITUCIONAL)
        | Q(visibilidad=Cuestionario.PRIVADO, cursos__in=cursos)
    ).distinct()


def cursos_para_presentar(user, cuestionario: Cuestionario, cuando=None) -> list[Curso]:
    """Cursos vigentes del estudiante en los que cuenta este cuestionario."""
    cursos = cursos_vigentes_del_estudiante(user, cuando)
    if not cuestionario.es_institucional:
        cursos = cursos.filter(id__in=cuestionario.cursos.values("id"))
    return list(cursos)


def puede_presentar(user, cuestionario: Cuestionario, cuando=None) -> bool:
    return cuestionario.es_institucional or bool(cursos_para_presentar(user, cuestionario, cuando))
