"""Módulo C: configuración y previsualización de cuestionarios."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import requiere_permiso
from core.services.acceso import es_personal_docente
from preguntas.models import Cuestionario, Pregunta
from preguntas.services import cuestionarios as servicio


@login_required
@requiere_permiso("cuestionarios.gestionar")
def cuestionarios_list(request):
    cuestionarios = list(
        Cuestionario.objects.prefetch_related("cuestionario_preguntas", "intentos").order_by("-id")
    )
    return render(request, "cuestionarios.html", {
        "cuestionarios": cuestionarios,
        "active_tab": "cuestionarios",
        **servicio.resumen_listado(cuestionarios),
    })


@login_required
@requiere_permiso("cuestionarios.gestionar")
def configurar_cuestionario(request, cuestionario_id=None):
    """Crear (sin id) o editar un cuestionario con sus preguntas asignadas."""
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id) if cuestionario_id else None

    if request.method == "POST":
        cuestionario = servicio.guardar_cuestionario(servicio.datos_desde_formulario(request.POST), cuestionario)
        messages.success(
            request,
            f"Cuestionario '{cuestionario.nombre}' guardado exitosamente ({cuestionario.get_estado_display()}).",
        )
        return redirect("preguntas:cuestionario_editar", cuestionario_id=cuestionario.id)

    asignadas, puntaje_total = servicio.preguntas_asignadas(cuestionario)
    return render(request, "configurar_cuestionario.html", {
        "cuestionario": cuestionario,
        "todas_preguntas": Pregunta.objects.filter(activa=True).select_related("categoria").order_by("categoria", "id"),
        "reactivos_asignados": asignadas,
        "puntaje_total": puntaje_total,
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
        return redirect("core:estudiante_dashboard")

    preguntas = servicio.serializar_preguntas(cuestionario, semilla=cuestionario.id, incluir_claves=True)
    return render(request, "cuestionario_previsualizar.html", {
        "cuestionario": cuestionario,
        "total_preguntas": len(preguntas),
        "preguntas_json": json.dumps(preguntas),
    })
