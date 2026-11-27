"""Módulo A: banco de preguntas."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from apps.core.decorators import requiere_permiso
from apps.banco_preguntas.models import Categoria, Pregunta
from apps.banco_preguntas import services as banco


POR_PAGINA = 15
FILTROS = ("q", "categoria", "tipo", "estado")


def _leer_filtros(datos):
    """Filtros válidos de la URL; los valores desconocidos se ignoran."""
    categoria = datos.get("categoria", "")
    return {
        "q": datos.get("q", "").strip()[:200],
        "categoria": int(categoria) if categoria.isdigit() else None,
        "tipo": datos.get("tipo") if datos.get("tipo") in dict(Pregunta.TIPO_CHOICES) else "",
        "estado": datos.get("estado") if datos.get("estado") in ("activas", "inactivas") else "",
    }


def _volver_al_banco(request):
    """Regresa al listado en la misma página y con los mismos filtros desde donde se actuó."""
    anterior = QueryDict(request.POST.get("volver", ""))
    conservar = {clave: anterior[clave] for clave in (*FILTROS, "page") if anterior.get(clave)}
    destino = reverse("banco_preguntas:banco")
    return redirect(f"{destino}?{urlencode(conservar)}" if conservar else destino)


@login_required
@requiere_permiso("preguntas.gestionar")
def banco_preguntas(request):
    """Consulta paginada del banco con búsqueda y filtros por competencia, tipo y estado."""
    filtros = _leer_filtros(request.GET)
    preguntas = (
        Pregunta.objects.select_related("categoria").prefetch_related("opciones")
        .annotate(n_cuestionarios=Count("cuestionario_preguntas", distinct=True))
        .order_by("-id")
    )
    if filtros["q"]:
        texto = filtros["q"]
        codigo = texto.upper().removeprefix("P-")
        coincide = Q(enunciado__icontains=texto) | Q(texto_base__icontains=texto)
        if codigo.isdigit():
            coincide |= Q(id=int(codigo))
        preguntas = preguntas.filter(coincide)
    if filtros["categoria"]:
        preguntas = preguntas.filter(categoria_id=filtros["categoria"])
    if filtros["tipo"]:
        preguntas = preguntas.filter(tipo=filtros["tipo"])
    if filtros["estado"]:
        preguntas = preguntas.filter(activa=filtros["estado"] == "activas")

    pagina = Paginator(preguntas, POR_PAGINA).get_page(request.GET.get("page"))
    return render(request, "banco_preguntas/banco.html", {
        "pagina": pagina,
        "filtros": filtros,
        "hay_filtros": any(filtros.values()),
        "total_banco": Pregunta.objects.count(),
        "categorias": Categoria.objects.all(),
        "tipos": Pregunta.TIPO_CHOICES,
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
    return _volver_al_banco(request)


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
    return _volver_al_banco(request)


@login_required
@requiere_permiso("preguntas.gestionar")
@require_POST
def toggle_pregunta_estado(request, pregunta_id):
    pregunta = banco.alternar_estado(get_object_or_404(Pregunta, id=pregunta_id))
    estado = "activada" if pregunta.activa else "desactivada"
    messages.success(request, f"Pregunta #{pregunta.id} {estado}.")
    return _volver_al_banco(request)
