"""Módulo A: banco de preguntas."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.decorators import requiere_permiso
from preguntas.models import Categoria, Pregunta
from preguntas.services import banco


@login_required
@requiere_permiso("preguntas.gestionar")
def banco_preguntas(request):
    """Consulta del banco de preguntas con filtros por competencia y tipo."""
    preguntas = (
        Pregunta.objects.select_related("categoria").prefetch_related("opciones").order_by("-id")
    )
    return render(request, "banco_preguntas.html", {
        "preguntas": preguntas,
        "categorias": Categoria.objects.all(),
    })


@login_required
@requiere_permiso("preguntas.gestionar")
def crear_pregunta(request):
    if request.method == "POST":
        try:
            pregunta = banco.guardar_pregunta(banco.datos_desde_formulario(request.POST))
            messages.success(request, f"Pregunta #{pregunta.id} registrada exitosamente.")
        except banco.PreguntaDuplicada:
            messages.error(request, "Error de duplicidad: Ya existe una pregunta idéntica en el banco.")
    return redirect("preguntas:banco")


@login_required
@requiere_permiso("preguntas.gestionar")
def editar_pregunta(request, pregunta_id):
    """GET: datos en JSON para el modal. POST: guarda los cambios."""
    pregunta = get_object_or_404(Pregunta, id=pregunta_id)
    if request.method != "POST":
        return JsonResponse(banco.serializar_para_edicion(pregunta))

    datos = banco.datos_desde_formulario(request.POST, tipo_por_defecto=pregunta.tipo)
    try:
        banco.guardar_pregunta(datos, pregunta)
        messages.success(request, f"Pregunta #{pregunta.id} actualizada exitosamente.")
    except banco.PreguntaDuplicada:
        messages.error(request, "Error de duplicidad: Ya existe otra pregunta con el mismo contenido.")
    return redirect("preguntas:banco")


@login_required
@requiere_permiso("preguntas.gestionar")
@require_POST
def toggle_pregunta_estado(request, pregunta_id):
    pregunta = banco.alternar_estado(get_object_or_404(Pregunta, id=pregunta_id))
    estado = "activada" if pregunta.activa else "desactivada"
    messages.success(request, f"Pregunta #{pregunta.id} {estado}.")
    return redirect("preguntas:banco")
