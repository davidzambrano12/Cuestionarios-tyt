"""Módulo C: configuración y previsualización de cuestionarios."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.decorators import requiere_permiso
from apps.core.services.acceso import es_personal_docente
from apps.banco_preguntas.models import Pregunta
from apps.cuestionarios.models import Cuestionario
from apps.cuestionarios import acceso
from apps.cuestionarios import services as servicio


@login_required
@requiere_permiso("cuestionarios.gestionar")
def cuestionarios_list(request):
    cuestionarios = list(
        acceso.visibles_para_docente(request.user)
        .select_related("creado_por").prefetch_related("cuestionario_preguntas", "intentos", "cursos__periodo")
        .order_by("-id")
    )
    for c in cuestionarios:
        c.editable = acceso.puede_editar(request.user, c)
    return render(request, "cuestionarios/listado.html", {
        "cuestionarios": cuestionarios,
        "active_tab": "cuestionarios",
        **servicio.resumen_listado(cuestionarios),
    })


def _preguntas_activas():
    return Pregunta.objects.filter(activa=True).select_related("categoria").order_by("categoria", "id")


@login_required
@requiere_permiso("cuestionarios.gestionar")
def configurar_cuestionario(request, cuestionario_id=None):
    """Crear (sin id) o editar un cuestionario con sus preguntas asignadas."""
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id) if cuestionario_id else None
    if cuestionario and not acceso.puede_editar(request.user, cuestionario):
        raise PermissionDenied("Este cuestionario lo gestiona otro docente o la institución.")
    cursos = list(acceso.cursos_asignables(request.user))
    actuales = list(cuestionario.cursos.values_list("id", flat=True)) if cuestionario else []
    contexto_visibilidad = {
        "puede_institucional": acceso.puede_publicar_institucional(request.user),
        "cursos_asignables": cursos,
        # Cursos ya asignados que el usuario no gestiona: se conservan
        "cursos_ajenos": (list(cuestionario.cursos.exclude(id__in=[c.id for c in cursos]).select_related("periodo"))
                          if cuestionario else []),
    }

    if request.method == "POST":
        try:
            datos = servicio.datos_desde_formulario(
                request.POST,
                puede_institucional=contexto_visibilidad["puede_institucional"],
                cursos_permitidos=[c.id for c in cursos],
                cursos_actuales=actuales,
            )
        except servicio.DatosInvalidos as error:
            # Se vuelve a mostrar el formulario con lo que escribió el docente
            for mensaje in error.errores:
                messages.error(request, mensaje)
            asignadas, puntaje_total = servicio.preguntas_por_ids(error.datos.preguntas_ids)
            return render(request, "cuestionarios/configurar.html", {
                "cuestionario": servicio.cuestionario_sin_guardar(error.datos, cuestionario),
                "todas_preguntas": _preguntas_activas(),
                "reactivos_asignados": asignadas,
                "puntaje_total": puntaje_total,
                "cursos_seleccionados": error.datos.cursos_ids,
                **contexto_visibilidad,
            }, status=400)
        if datos.visibilidad == Cuestionario.PRIVADO:
            # Los cursos asignados por otra persona (que el usuario no gestiona) se conservan
            datos.cursos_ids = sorted(set(datos.cursos_ids) | {c.id for c in contexto_visibilidad["cursos_ajenos"]})
        cuestionario = servicio.guardar_cuestionario(datos, cuestionario, usuario=request.user)
        messages.success(
            request,
            f"Cuestionario '{cuestionario.nombre}' guardado exitosamente ({cuestionario.get_estado_display()}).",
        )
        return redirect("cuestionarios:editar", cuestionario_id=cuestionario.id)

    asignadas, puntaje_total = servicio.preguntas_asignadas(cuestionario)
    return render(request, "cuestionarios/configurar.html", {
        "cuestionario": cuestionario,
        "todas_preguntas": _preguntas_activas(),
        "reactivos_asignados": asignadas,
        "puntaje_total": puntaje_total,
        "cursos_seleccionados": actuales,
        **contexto_visibilidad,
    })


@login_required
def previsualizar_cuestionario(request, cuestionario_id):
    """
    Recorrido simulado del examen para docentes, con claves y retroalimentación,
    sin registrar intentos ni alterar estadísticas.
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    if not es_personal_docente(request.user):
        messages.error(request, "Acceso no autorizado: la previsualización de evaluaciones es exclusiva para el cuerpo docente.")
        return redirect("evaluaciones:panel_estudiante")
    if not acceso.puede_ver_como_docente(request.user, cuestionario):
        raise PermissionDenied("Este cuestionario es de un curso de otro docente.")

    preguntas = servicio.serializar_preguntas(cuestionario, semilla=cuestionario.id, incluir_claves=True)
    return render(request, "cuestionarios/previsualizar.html", {
        "cuestionario": cuestionario,
        "total_preguntas": len(preguntas),
        "preguntas": preguntas,
    })


def landing(request):
    """Página de inicio pública del Simulador Saber TyT Uniputumayo."""
    ahora = timezone.now()
    cuestionarios = Cuestionario.objects.filter(
        visibilidad=Cuestionario.INSTITUCIONAL,  # los de curso no se anuncian en la portada pública
        estado="disponible",
        fecha_apertura__lte=ahora,
        fecha_cierre__gte=ahora,
    ).order_by("-id")
    return render(request, "cuestionarios/landing.html", {"cuestionarios": cuestionarios})
