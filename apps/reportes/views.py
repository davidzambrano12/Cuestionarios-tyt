"""Reporte de intentos por cuestionario (CU-05), reintentos y exportación a Excel."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import requiere_permiso, solo_roles
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
    """Panel del administrador con métricas globales del sistema."""
    return render(request, "reportes/panel_admin.html", reportes.panel_admin())


@login_required
@requiere_permiso("preguntas.gestionar")
def panel_docente(request):
    """Panel del docente con su resumen de cuestionarios y banco."""
    return render(request, "reportes/panel_docente.html", reportes.panel_docente())


# ---------------------------------------------------------------------------
# Consultas y reportes (filtros jerárquicos y exportación)
# ---------------------------------------------------------------------------

@login_required
@requiere_permiso("resultados.consultar_todos")
def consultas(request):
    from django.core.paginator import Paginator

    from apps.reportes import consultas as c
    from apps.reportes.templatetags.consultas import nota, porcentaje

    alcance = c.alcance_de(request.user)
    catalogo = c.catalogo(alcance)
    filtros = c.leer_filtros(request.GET, alcance, catalogo)
    for aviso in filtros.avisos:
        messages.warning(request, aviso)

    # Un estudiante consultado por el administrador que no tiene matrícula sigue en la lista
    if filtros.estudiante and filtros.estudiante not in {e["codigo"] for e in catalogo["estudiantes"]}:
        catalogo["estudiantes"].append({"codigo": filtros.estudiante, "cursos": [], "periodos": [], "anios": [],
                                        "nombre": filtros.etiquetas["estudiante"].rsplit(" (", 1)[0]})

    qs = c.intentos_filtrados(filtros, alcance)
    ind = c.indicadores(qs)
    textos = {
        "promedio": nota(ind["promedio"]),
        "rango": f"Mínima {nota(ind['minima'])} · Máxima {nota(ind['maxima'])}",
        "aprobacion": porcentaje(ind["porcentaje_aprobacion"]),
        "aprobados": f"{ind['aprobados']} aprobados · {ind['no_aprobados']} no aprobados",
    }
    contexto = {
        "textos": textos,
        "active_tab": "consultas",
        "filtros": filtros,
        "catalogo": catalogo,
        "alcance": alcance,
        "indicadores": ind,
        "ordenes": [("fecha", "Fecha (más reciente)"), ("nombre", "Nombre (A–Z)"), ("nota", "Calificación (mayor a menor)")],
    }
    vista = filtros.vista
    if vista == "calificaciones":
        pagina = Paginator(c.calificaciones(qs, filtros.orden), c.POR_PAGINA).get_page(request.GET.get("page"))
        for intento in pagina:
            intento.nota_5 = c._redondear(intento.nota)
            intento.estado_texto = c.estado_legible(intento)
        contexto["pagina"] = pagina
    elif vista == "periodos":
        contexto["filas"] = c.por_periodo(qs)
    elif vista == "cursos":
        contexto["filas"] = c.por_curso(qs)
    elif vista == "ejes":
        contexto["filas"] = c.por_eje(qs, filtros)
    elif vista == "historial" and filtros.estudiante:
        contexto["historial"] = c.historial(qs, filtros)
        for intento in contexto["historial"]:
            intento.estado_texto = c.estado_legible(intento)
    elif vista == "dificultad":
        pagina = Paginator(c.dificultad(qs, filtros), c.POR_PAGINA).get_page(request.GET.get("page"))
        pagina.filas = [c.fila_dificultad(f) for f in pagina]
        contexto["pagina"] = pagina
    return render(request, "reportes/consultas.html", contexto)


@login_required
@requiere_permiso("resultados.consultar_todos")
def exportar_consulta(request, reporte):
    """Excel A, B o C con exactamente los filtros y permisos de la consulta."""
    from django.http import Http404

    from apps.reportes import consultas as c
    from apps.reportes import exportar

    if reporte not in exportar.LIBROS:
        raise Http404("Reporte desconocido.")
    alcance = c.alcance_de(request.user)
    filtros = c.leer_filtros(request.GET, alcance)
    libro = exportar.LIBROS[reporte](filtros, alcance)
    response = HttpResponse(content_type=TIPO_XLSX)
    response["Content-Disposition"] = f'attachment; filename="{exportar.nombre_archivo(reporte, filtros)}"'
    libro.save(response)
    return response
