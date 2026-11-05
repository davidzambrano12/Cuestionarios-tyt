"""Módulos D y E: sala de examen, autoguardado, entrega y resultado."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.formats import localize

from apps.core.services.acceso import es_dueno_del_intento, es_personal_docente, puede_auditar_resultados
from apps.cuestionarios.models import Cuestionario
from apps.evaluaciones.models import Intento
from apps.evaluaciones import services as servicio
from apps.cuestionarios.services import serializar_preguntas


def _puede_operar(user, intento) -> bool:
    return es_dueno_del_intento(user, intento) or user.is_superuser


@login_required
def iniciar_evaluacion(request, cuestionario_id):
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)

    # Los docentes previsualizan para no alterar las estadísticas estudiantiles
    if es_personal_docente(request.user):
        messages.info(request, "Acceso como docente: Has sido redirigido al modo de previsualización para no alterar las estadísticas estudiantiles.")
        return redirect("cuestionarios:previsualizar", cuestionario_id=cuestionario.id)

    resultado = servicio.iniciar_intento(request.user, cuestionario)
    if resultado.tipo == "rechazado":
        messages.error(request, resultado.mensaje)
        return redirect("evaluaciones:panel_estudiante")
    if resultado.tipo == "vencido":
        messages.warning(request, resultado.mensaje)
        return redirect("evaluaciones:resultado", intento_id=resultado.intento.id)
    if resultado.mensaje:
        messages.info(request, resultado.mensaje)
    return redirect("evaluaciones:sala", intento_id=resultado.intento.id)


@login_required
def evaluacion_en_vivo(request, intento_id):
    intento = get_object_or_404(Intento.objects.select_related("cuestionario"), id=intento_id)
    if not _puede_operar(request.user, intento):
        return HttpResponseForbidden("Acceso denegado: este intento no pertenece a su usuario.")
    if intento.estado != "en_progreso":
        return redirect("evaluaciones:resultado", intento_id=intento.id)
    if servicio.cerrar_si_vencio(intento):
        messages.warning(request, "El tiempo límite para este examen ha vencido.")
        return redirect("evaluaciones:resultado", intento_id=intento.id)

    preguntas = serializar_preguntas(intento.cuestionario, semilla=intento.id, incluir_claves=False)
    respuestas_previas = dict(
        intento.respuestas.filter(opcion_seleccionada__isnull=False)
        .values_list("pregunta_id", "opcion_seleccionada_id")
    )
    return render(request, "evaluaciones/sala.html", {
        "intento": intento,
        "cuestionario": intento.cuestionario,
        "total_preguntas": len(preguntas),
        "preguntas": preguntas,
        "respuestas_previas": respuestas_previas,
        "segundos_restantes": servicio.segundos_restantes(intento),
    })


@login_required
def guardar_respuesta_ajax(request, intento_id):
    """Autoguardado (fetch) de cada selección para resistir recargas o caídas de red."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    intento = get_object_or_404(Intento.objects.select_related("cuestionario"), id=intento_id)
    if not _puede_operar(request.user, intento):
        return JsonResponse({"error": "No autorizado"}, status=403)
    if intento.estado != "en_progreso":
        return JsonResponse({"error": "El examen ya no está activo"}, status=400)

    try:
        data = json.loads(request.body)
        servicio.guardar_respuesta(
            intento,
            pregunta_id=int(data.get("pregunta_id")),
            opcion_id=data.get("opcion_id"),
            marcada=bool(data.get("marcada_para_revision", False)),
        )
    except Exception as exc:  # datos mal formados o pregunta inexistente
        return JsonResponse({"status": "error", "mensaje": str(exc)}, status=400)
    return JsonResponse({"status": "ok", "guardado": True})


@login_required
def finalizar_evaluacion(request, intento_id):
    intento = get_object_or_404(Intento.objects.select_related("cuestionario"), id=intento_id)
    if not _puede_operar(request.user, intento):
        return HttpResponseForbidden("Acceso denegado a este intento.")
    if intento.estado == "finalizado" or request.method != "POST":
        return redirect(
            "evaluaciones:resultado" if intento.estado == "finalizado" else "evaluaciones:sala",
            intento_id=intento.id,
        )

    try:
        respuestas = json.loads(request.POST.get("respuestas_json", "{}"))
    except (TypeError, ValueError):
        respuestas = {}
    intento = servicio.calificar_intento(intento, respuestas if isinstance(respuestas, dict) else {})

    messages.success(
        request,
        f"¡Evaluación completada! Calificación obtenida: {localize(intento.calificacion)} / {localize(intento.cuestionario.calificacion_maxima)}",
    )
    return redirect("evaluaciones:resultado", intento_id=intento.id)


@login_required
def resultado_evaluacion(request, intento_id):
    """Calificación final y, si está permitido, la revisión pedagógica desglosada."""
    intento = get_object_or_404(Intento.objects.select_related("cuestionario"), id=intento_id)
    es_auditor = puede_auditar_resultados(request.user)
    if not es_dueno_del_intento(request.user, intento) and not es_auditor:
        return HttpResponseForbidden("Acceso denegado a este reporte.")

    permitir_revision = intento.cuestionario.permitir_revision or es_auditor or request.user.is_staff
    return render(request, "evaluaciones/resultado.html", {
        "intento": intento,
        "cuestionario": intento.cuestionario,
        "permitir_revision": permitir_revision,
        "es_auditor": es_auditor,
        "dictamen": servicio.dictamen_intento(intento, intento.cuestionario),
        **servicio.revision_intento(intento, detallada=permitir_revision),
    })


@login_required
def panel_estudiante(request):
    """Panel del estudiante: cuestionarios vigentes, programados e historial propio."""
    return render(request, "evaluaciones/panel_estudiante.html", servicio.panel_estudiante(request.user))
