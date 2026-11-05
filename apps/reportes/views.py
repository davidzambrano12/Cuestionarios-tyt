"""Reporte de intentos por cuestionario (CU-05), reintentos y exportación a Excel."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import requiere_permiso, solo_roles
from apps.banco_preguntas.models import Categoria, Pregunta
from apps.cuestionarios.models import Cuestionario
from apps.evaluaciones.models import Intento
from apps.reportes import services as reportes

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@login_required
@requiere_permiso("cuestionarios.gestionar")
def cuestionario_intentos(request, cuestionario_id):
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    return render(request, "reportes/intentos.html", {
        "cuestionario": cuestionario,
        "active_tab": "cuestionarios",
        **reportes.reporte_intentos(cuestionario),
    })


@login_required
@requiere_permiso("cuestionarios.gestionar")
def exportar_intentos_excel(request, cuestionario_id):
    """Descarga el reporte en .xlsx; `?q=` exporta solo la búsqueda del docente."""
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    libro, nombre_archivo = reportes.libro_excel_intentos(cuestionario, request.GET.get("q", ""))
    response = HttpResponse(content_type=TIPO_XLSX)
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    libro.save(response)
    return response


@login_required
@requiere_permiso("cuestionarios.gestionar")
def reiniciar_estudiante_cuestionario(request, cuestionario_id, codigo_estudiante):
    """Elimina todos los intentos de un estudiante y le restaura el cupo completo."""
    if request.method == "POST":
        cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
        with transaction.atomic():
            eliminados, _ = Intento.objects.filter(
                cuestionario=cuestionario, participante_codigo=codigo_estudiante,
            ).delete()
        messages.success(
            request,
            f"Se han reiniciado los {eliminados} intentos del estudiante ({codigo_estudiante}). Su cupo ha quedado totalmente restaurado.",
        )
    return redirect("reportes:intentos", cuestionario_id=cuestionario_id)


@login_required
@requiere_permiso("cuestionarios.gestionar")
def reiniciar_intento(request, intento_id):
    """Anula un intento puntual (caída de red, fuerza mayor) y devuelve ese cupo."""
    if request.method != "POST":
        return redirect("cuestionarios:listado")
    intento = get_object_or_404(Intento, id=intento_id)
    cuestionario_id = intento.cuestionario_id
    with transaction.atomic():
        intento.delete()  # sus respuestas_intento se eliminan en cascada
    messages.success(
        request,
        f"Se ha reiniciado con éxito el intento de {intento.participante_nombre} ({intento.participante_codigo}). El estudiante ahora cuenta con su cupo restaurado para presentar nuevamente la prueba.",
    )
    return redirect("reportes:intentos", cuestionario_id=cuestionario_id)


# ------------------------------------------------------------------------------
# Paneles de inicio con métricas generales
# ------------------------------------------------------------------------------

@login_required
@solo_roles("admin")
def panel_admin(request):
    """Dashboard para el Administrador del Sistema."""
    preguntas_activas = Pregunta.objects.filter(activa=True).count()
    categorias = Categoria.objects.all()
    cuestionarios_count = Cuestionario.objects.count()
    intentos_count = Intento.objects.count()
    cuestionarios_recientes = Cuestionario.objects.all().order_by("-id")[:5]

    return render(request, "reportes/panel_admin.html", {
        "preguntas_activas": preguntas_activas,
        "categorias_count": categorias.count(),
        "categorias_list": categorias,
        "cuestionarios_count": cuestionarios_count,
        "intentos_count": intentos_count,
        "cuestionarios_recientes": cuestionarios_recientes,
    })


@login_required
@requiere_permiso("preguntas.gestionar")
def panel_docente(request):
    """Dashboard para Docentes y Evaluadores."""
    cuestionarios = Cuestionario.objects.all().order_by("-id")
    preguntas_count = Pregunta.objects.filter(activa=True).count()
    publicados_count = Cuestionario.objects.filter(estado="disponible").count()

    return render(request, "reportes/panel_docente.html", {
        "cuestionarios": cuestionarios,
        "preguntas_count": preguntas_count,
        "publicados_count": publicados_count,
        "cuestionarios_recientes": cuestionarios[:4],
    })
