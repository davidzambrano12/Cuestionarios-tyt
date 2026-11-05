"""Cursos y matrículas: el administrador gestiona todos; el docente, los que tiene a cargo."""
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import requiere_permiso
from apps.core.services.acceso import codigo_participante

from . import services
from .forms import CursoForm, PeriodoForm
from .models import Curso, Matricula, PeriodoAcademico

LIMITE_BUSQUEDA = 20


def _curso_gestionable(request, curso_id) -> Curso:
    curso = get_object_or_404(Curso.objects.select_related("periodo", "docente"), id=curso_id)
    if not services.puede_gestionar(request.user, curso):
        raise PermissionDenied("Este curso está a cargo de otro docente.")
    return curso


@login_required
@requiere_permiso("cursos.gestionar")
def listado(request):
    cursos = services.cursos_visibles(request.user).annotate(
        num_matriculados=Count("matriculas", distinct=True),
        num_intentos=Count("intentos", distinct=True),
    )
    periodos = PeriodoAcademico.objects.order_by("-anio", "-numero")
    periodo_id = request.GET.get("periodo", "")
    if periodo_id.isdigit():
        cursos = cursos.filter(periodo_id=int(periodo_id))
    q = request.GET.get("q", "").strip()
    if q:
        cursos = cursos.filter(Q(asignatura__icontains=q) | Q(grupo__icontains=q) | Q(programa__icontains=q))
    es_admin = services.es_admin(request.user)
    return render(request, "academico/listado.html", {
        "active_tab": "cursos",
        "cursos": cursos.order_by("-periodo__anio", "-periodo__numero", "asignatura", "grupo"),
        "periodos": periodos,
        "periodo_id": int(periodo_id) if periodo_id.isdigit() else None,
        "q": q,
        "es_admin": es_admin,
        "form_periodo": PeriodoForm(),
        "sin_curso": services.resumen_sin_curso() if es_admin else None,
    })


@login_required
@requiere_permiso("cursos.gestionar")
def crear_periodo(request):
    if not services.es_admin(request.user):
        raise PermissionDenied("Solo un administrador crea períodos académicos.")
    if request.method != "POST":
        return redirect("academico:listado")
    form = PeriodoForm(request.POST)
    if form.is_valid():
        periodo = form.save()
        messages.success(request, f"Período {periodo} creado.")
    else:
        errores = "; ".join(e for lista in form.errors.values() for e in lista)
        messages.error(request, f"No se creó el período: {errores}")
    return redirect("academico:listado")


def _formulario_curso(request, curso=None):
    elige_docente = services.es_admin(request.user)
    form = CursoForm(request.POST or None, instance=curso, puede_elegir_docente=elige_docente)
    if request.method == "POST" and form.is_valid():
        nuevo = form.save(commit=False)
        if not elige_docente:
            nuevo.docente = request.user
        nuevo.save()
        messages.success(request, f"Curso «{nuevo.nombre}» guardado.")
        return redirect("academico:detalle", curso_id=nuevo.id)
    if not PeriodoAcademico.objects.exists():
        messages.warning(request, "Primero un administrador debe crear el período académico.")
    return render(request, "academico/curso_form.html", {
        "active_tab": "cursos", "form": form, "curso": curso,
    })


@login_required
@requiere_permiso("cursos.gestionar")
def crear_curso(request):
    return _formulario_curso(request)


@login_required
@requiere_permiso("cursos.gestionar")
def editar_curso(request, curso_id):
    return _formulario_curso(request, _curso_gestionable(request, curso_id))


@login_required
@requiere_permiso("cursos.gestionar")
def detalle(request, curso_id):
    from decimal import Decimal

    from apps.evaluaciones.models import Intento

    curso = _curso_gestionable(request, curso_id)
    matriculas = list(curso.matriculas.select_related("estudiante__perfil").order_by(
        "estudiante__first_name", "estudiante__last_name"))
    intentos_por_codigo = dict(
        Intento.objects.filter(curso=curso).values("participante_codigo")
        .annotate(n=Count("id")).values_list("participante_codigo", "n")
    )
    # Última nota (sobre 5,0) de cada estudiante en este curso
    ultima_nota = {}
    for codigo, nota, maxima in (
        Intento.objects.filter(curso=curso, estado__in=("finalizado", "vencido"), calificacion__isnull=False)
        .order_by("-fecha_inicio").values_list("participante_codigo", "calificacion", "cuestionario__calificacion_maxima")
    ):
        if codigo not in ultima_nota:
            ultima_nota[codigo] = (nota * Decimal("5") / maxima).quantize(Decimal("0.01"))
    for m in matriculas:
        m.codigo = codigo_participante(m.estudiante)
        m.num_intentos = intentos_por_codigo.get(m.codigo, 0)
        m.ultima_nota = ultima_nota.get(m.codigo)
        m.inicial = (m.estudiante.first_name or m.estudiante.username)[:1].upper()
    con_intentos = sum(1 for m in matriculas if m.num_intentos)
    return render(request, "academico/detalle.html", {
        "active_tab": "cursos",
        "curso": curso,
        "matriculas": matriculas,
        "resumen": {"total": len(matriculas), "con_intentos": con_intentos, "sin_intentos": len(matriculas) - con_intentos},
        "url_historial": (f"{reverse('reportes:consultas')}?anio={curso.periodo.anio}&periodo={curso.periodo_id}"
                          f"&curso={curso.id}&vista=historial&estudiante="),
    })


def _candidato(est, otros) -> dict:
    return {
        "id": est.id,
        "nombre": est.get_full_name() or est.username,
        "codigo": codigo_participante(est),
        "otro_curso": otros.get(est.id, ""),
    }


def _otros_cursos(curso, estudiantes) -> dict:
    """Otro curso del mismo período en que ya está cada estudiante (para avisar)."""
    return dict(
        Matricula.objects.filter(estudiante__in=estudiantes, curso__periodo=curso.periodo)
        .exclude(curso=curso).values_list("estudiante_id", "curso__asignatura")
    )


@login_required
@requiere_permiso("cursos.gestionar")
def buscar_estudiantes(request, curso_id):
    """Búsqueda en vivo (JSON): estudiantes activos que aún no están en el curso."""
    from django.http import JsonResponse

    curso = _curso_gestionable(request, curso_id)
    q = request.GET.get("q", "").strip()[:60]
    if len(q) < 2:
        return JsonResponse({"resultados": [], "mas": False})
    consulta = services.estudiantes_elegibles().exclude(matriculas__curso=curso).filter(
        Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q)
        | Q(perfil__codigo_institucional__icontains=q) | Q(perfil__documento_identidad__icontains=q)
    )
    estudiantes = list(consulta[:LIMITE_BUSQUEDA + 1])
    mas = len(estudiantes) > LIMITE_BUSQUEDA
    estudiantes = estudiantes[:LIMITE_BUSQUEDA]
    otros = _otros_cursos(curso, estudiantes)
    return JsonResponse({"resultados": [_candidato(e, otros) for e in estudiantes], "mas": mas})


MAX_CODIGOS = 500


@login_required
@requiere_permiso("cursos.gestionar")
def revisar_codigos(request, curso_id):
    """
    Revisa una lista pegada de códigos (JSON): cuáles corresponden a estudiantes,
    cuáles no existen y cuáles ya están en el curso. No matricula a nadie.
    """
    from django.http import JsonResponse

    curso = _curso_gestionable(request, curso_id)
    if request.method != "POST":
        return JsonResponse({"detail": "Método no permitido."}, status=405)
    codigos = list(dict.fromkeys(c for c in re.split(r"[\s,;]+", request.POST.get("codigos", "")) if c))
    if len(codigos) > MAX_CODIGOS:
        return JsonResponse({"detail": f"Pega como máximo {MAX_CODIGOS} códigos por vez."}, status=400)

    por_codigo = {}
    for est in services.estudiantes_elegibles().filter(
        Q(perfil__codigo_institucional__in=codigos) | Q(username__in=codigos)
    ):
        por_codigo.setdefault(codigo_participante(est), est)
        por_codigo.setdefault(est.username, est)
    ya = set(curso.matriculas.values_list("estudiante_id", flat=True))

    encontrados, ya_matriculados, no_existen, vistos = [], [], [], set()
    for codigo in codigos:
        est = por_codigo.get(codigo)
        if not est:
            no_existen.append(codigo)
        elif est.id in ya:
            ya_matriculados.append(codigo)
        elif est.id not in vistos:
            vistos.add(est.id)
            encontrados.append(est)
    otros = _otros_cursos(curso, encontrados)
    return JsonResponse({
        "encontrados": [_candidato(e, otros) for e in encontrados],
        "no_existen": no_existen,
        "ya_matriculados": ya_matriculados,
    })


@login_required
@requiere_permiso("cursos.gestionar")
def matricular(request, curso_id):
    curso = _curso_gestionable(request, curso_id)
    if request.method != "POST":
        return redirect("academico:detalle", curso_id=curso.id)
    if not curso.activo:
        messages.error(request, "El curso está inactivo: no admite matrículas nuevas.")
        return redirect("academico:detalle", curso_id=curso.id)
    ids = [int(i) for i in request.POST.getlist("estudiantes") if i.isdigit()]
    estudiantes = list(services.estudiantes_elegibles().filter(id__in=ids))
    if not estudiantes:
        messages.warning(request, "Selecciona al menos un estudiante.")
        return redirect("academico:detalle", curso_id=curso.id)

    r = services.matricular(curso, estudiantes)
    if r["nuevos"]:
        texto = f"{len(r['nuevos'])} estudiante{'s' if len(r['nuevos']) != 1 else ''} matriculado{'s' if len(r['nuevos']) != 1 else ''}."
        if r["intentos_asignados"]:
            texto += f" {r['intentos_asignados']} intento(s) anteriores de este período quedaron asociados al curso."
        messages.success(request, texto)
    if r["en_otro_curso"]:
        nombres = ", ".join(e.get_full_name() or e.username for e in r["en_otro_curso"])
        messages.warning(request, f"{nombres} ya está(n) en otro curso de {curso.periodo}: sus intentos nuevos "
                                  "se asignarán a uno solo (el primero en orden alfabético).")
    if r["ya_estaban"]:
        messages.info(request, f"{len(r['ya_estaban'])} ya estaba(n) matriculado(s).")
    return redirect("academico:detalle", curso_id=curso.id)


@login_required
@requiere_permiso("cursos.gestionar")
def retirar(request, curso_id, matricula_id):
    curso = _curso_gestionable(request, curso_id)
    matricula = get_object_or_404(Matricula.objects.select_related("estudiante", "curso"), id=matricula_id, curso=curso)
    if request.method == "POST":
        nombre = matricula.estudiante.get_full_name() or matricula.estudiante.username
        try:
            services.retirar(matricula)
            messages.success(request, f"{nombre} fue retirado del curso.")
        except services.RetiroNoPermitido as error:
            messages.error(request, str(error))
    return redirect(f"{reverse('academico:detalle', args=[curso.id])}#matriculados")
