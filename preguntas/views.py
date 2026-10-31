import json
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.decorators import requiere_permiso
from .forms import ImportarPreguntasForm
from .models import (
    Categoria,
    Cuestionario,
    CuestionarioPregunta,
    Intento,
    OpcionRespuesta,
    Pregunta,
    RespuestaIntento,
)
from .services.importador_excel import (
    _validar_fila,
    actualizar_fila_excel,
    calcular_huella,
    procesar_archivo,
)

CARPETA_TEMPORAL = "importaciones_tmp"


# ==============================================================================
# BANCO DE PREGUNTAS
# ==============================================================================

@login_required
@requiere_permiso("preguntas.gestionar")
def banco_preguntas(request):
    """Consulta del banco de preguntas con filtros por competencia y tipo."""
    preguntas = Pregunta.objects.all().select_related("categoria").prefetch_related("opciones").order_by("-id")
    categorias = Categoria.objects.all()

    return render(request, "banco_preguntas.html", {
        "preguntas": preguntas,
        "categorias": categorias,
    })


@login_required
@requiere_permiso("preguntas.gestionar")
def crear_pregunta(request):
    """Crea una nueva pregunta con sus opciones y verificación de duplicados."""
    if request.method == "POST":
        categoria_id = request.POST.get("categoria_id")
        tipo = request.POST.get("tipo", Pregunta.TIPO_MULTIPLE)
        texto_base = request.POST.get("texto_base", "").strip() or None
        enunciado = request.POST.get("enunciado", "").strip()
        puntaje_val = request.POST.get("puntaje", "1.00")
        retroalimentacion = request.POST.get("retroalimentacion", "").strip() or None

        try:
            puntaje = Decimal(puntaje_val)
        except Exception:
            puntaje = Decimal("1.00")

        # Preparar opciones según el tipo
        opciones_data = []
        if tipo == Pregunta.TIPO_MULTIPLE:
            op_a = request.POST.get("opcion_a", "").strip()
            op_b = request.POST.get("opcion_b", "").strip()
            op_c = request.POST.get("opcion_c", "").strip()
            op_d = request.POST.get("opcion_d", "").strip()
            correcta = request.POST.get("correcta", "A")

            opciones_data = [
                (op_a, correcta == "A", 1),
                (op_b, correcta == "B", 2),
                (op_c, correcta == "C", 3),
                (op_d, correcta == "D", 4),
            ]
        else:
            correcta_vf = request.POST.get("correcta_vf", "V")
            opciones_data = [
                ("Verdadero", correcta_vf == "V", 1),
                ("Falso", correcta_vf == "F", 2),
            ]

        # Calcular huella SHA-256 para evitar duplicados
        textos_opciones = [o[0] for o in opciones_data]
        huella = calcular_huella(enunciado, textos_opciones)

        if Pregunta.objects.filter(huella_contenido=huella).exists():
            messages.error(request, "Error de duplicidad: Ya existe una pregunta idéntica en el banco.")
            return redirect("/preguntas/")

        with transaction.atomic():
            categoria = Categoria.objects.get(id=categoria_id)
            pregunta = Pregunta.objects.create(
                categoria=categoria,
                tipo=tipo,
                texto_base=texto_base,
                enunciado=enunciado,
                retroalimentacion=retroalimentacion,
                puntaje=puntaje,
                huella_contenido=huella,
                activa=True,
            )

            for texto_op, es_corr, ord_num in opciones_data:
                OpcionRespuesta.objects.create(
                    pregunta=pregunta,
                    texto=texto_op,
                    es_correcta=es_corr,
                    orden=ord_num,
                )

        messages.success(request, f"Pregunta #{pregunta.id} registrada exitosamente.")
    return redirect("/preguntas/")


@login_required
@requiere_permiso("preguntas.gestionar")
def editar_pregunta(request, pregunta_id):
    """Permite consultar y actualizar una pregunta existente en el banco."""
    pregunta = get_object_or_404(Pregunta, id=pregunta_id)

    if request.method == "POST":
        categoria_id = request.POST.get("categoria_id")
        tipo = request.POST.get("tipo", pregunta.tipo)
        texto_base = request.POST.get("texto_base", "").strip() or None
        enunciado = request.POST.get("enunciado", "").strip()
        puntaje_val = request.POST.get("puntaje", "1.00")
        retroalimentacion = request.POST.get("retroalimentacion", "").strip() or None

        try:
            puntaje = Decimal(puntaje_val)
        except Exception:
            puntaje = Decimal("1.00")

        opciones_data = []
        if tipo == Pregunta.TIPO_MULTIPLE:
            op_a = request.POST.get("opcion_a", "").strip()
            op_b = request.POST.get("opcion_b", "").strip()
            op_c = request.POST.get("opcion_c", "").strip()
            op_d = request.POST.get("opcion_d", "").strip()
            correcta = request.POST.get("correcta", "A")

            opciones_data = [
                (op_a, correcta == "A", 1),
                (op_b, correcta == "B", 2),
                (op_c, correcta == "C", 3),
                (op_d, correcta == "D", 4),
            ]
        else:
            correcta_vf = request.POST.get("correcta_vf", "V")
            opciones_data = [
                ("Verdadero", correcta_vf == "V", 1),
                ("Falso", correcta_vf == "F", 2),
            ]

        # Validar huella de duplicados excluyendo la pregunta actual
        textos_opciones = [o[0] for o in opciones_data]
        huella = calcular_huella(enunciado, textos_opciones)

        if Pregunta.objects.filter(huella_contenido=huella).exclude(id=pregunta.id).exists():
            messages.error(request, "Error de duplicidad: Ya existe otra pregunta con el mismo contenido.")
            return redirect("/preguntas/")

        with transaction.atomic():
            categoria = Categoria.objects.get(id=categoria_id)
            pregunta.categoria = categoria
            pregunta.tipo = tipo
            pregunta.texto_base = texto_base
            pregunta.enunciado = enunciado
            pregunta.retroalimentacion = retroalimentacion
            pregunta.puntaje = puntaje
            pregunta.huella_contenido = huella
            pregunta.save()

            # Actualizar opciones
            pregunta.opciones.all().delete()
            for texto_op, es_corr, ord_num in opciones_data:
                OpcionRespuesta.objects.create(
                    pregunta=pregunta,
                    texto=texto_op,
                    es_correcta=es_corr,
                    orden=ord_num,
                )

        messages.success(request, f"Pregunta #{pregunta.id} actualizada exitosamente.")
        return redirect("/preguntas/")

    # Respuesta JSON para cargar en modal vía AJAX
    opciones = list(pregunta.opciones.order_by("orden", "id").values("id", "texto", "es_correcta", "orden"))
    return JsonResponse({
        "id": pregunta.id,
        "categoria_id": pregunta.categoria_id,
        "tipo": pregunta.tipo,
        "texto_base": pregunta.texto_base or "",
        "enunciado": pregunta.enunciado,
        "puntaje": str(pregunta.puntaje),
        "retroalimentacion": pregunta.retroalimentacion or "",
        "opciones": opciones,
    })


@login_required
@requiere_permiso("preguntas.gestionar")
def toggle_pregunta_estado(request, pregunta_id):
    """Activa o desactiva un reactivo en el banco."""
    if request.method == "POST":
        p = get_object_or_404(Pregunta, id=pregunta_id)
        p.activa = not p.activa
        p.save()
        estado = "activada" if p.activa else "desactivada"
        messages.success(request, f"Pregunta #{p.id} {estado}.")
    return redirect("/preguntas/")


# ==============================================================================
# CONFIGURACIÓN DE CUESTIONARIOS
# ==============================================================================

@login_required
@requiere_permiso("cuestionarios.gestionar")
def cuestionarios_list(request):
    """Lista completa de cuestionarios institucionales con filtros y métricas."""
    cuestionarios = (
        Cuestionario.objects.all()
        .prefetch_related("cuestionario_preguntas", "intentos")
        .order_by("-id")
    )
    total_count = cuestionarios.count()
    disponibles_count = sum(1 for c in cuestionarios if c.esta_vigente)
    borradores_count = cuestionarios.filter(estado="borrador").count()
    cerrados_count = sum(1 for c in cuestionarios if c.esta_vencido)

    return render(
        request,
        "cuestionarios.html",
        {
            "cuestionarios": cuestionarios,
            "total_count": total_count,
            "disponibles_count": disponibles_count,
            "borradores_count": borradores_count,
            "cerrados_count": cerrados_count,
            "active_tab": "cuestionarios",
        },
    )


@login_required
@requiere_permiso("cuestionarios.gestionar")
def configurar_cuestionario(request, cuestionario_id=None):
    """Crear o editar un cuestionario con sus 5 secciones reglamentarias."""
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id) if cuestionario_id else None
    todas_preguntas = Pregunta.objects.filter(activa=True).select_related("categoria").order_by("categoria", "id")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        fecha_apertura = request.POST.get("fecha_apertura")
        fecha_cierre = request.POST.get("fecha_cierre")
        tiempo_limite = int(request.POST.get("tiempo_limite_minutos", 120))
        intentos = int(request.POST.get("intentos_permitidos", 5))
        calif_max = Decimal(request.POST.get("calificacion_maxima", "5.00"))
        calif_apr = Decimal(request.POST.get("calificacion_aprobacion", "3.00"))
        mezclar_p = bool(request.POST.get("mezclar_preguntas"))
        mezclar_r = bool(request.POST.get("mezclar_respuestas"))
        permitir_rev = bool(request.POST.get("permitir_revision"))
        accion = request.POST.get("accion", "borrador")
        nuevo_estado = "disponible" if accion == "publicar" else "borrador"

        preguntas_ids = request.POST.getlist("preguntas_ids")

        with transaction.atomic():
            if cuestionario:
                cuestionario.nombre = nombre
                cuestionario.descripcion = descripcion
                cuestionario.fecha_apertura = fecha_apertura
                cuestionario.fecha_cierre = fecha_cierre
                cuestionario.tiempo_limite_minutos = tiempo_limite
                cuestionario.intentos_permitidos = intentos
                cuestionario.calificacion_maxima = calif_max
                cuestionario.calificacion_aprobacion = calif_apr
                cuestionario.mezclar_preguntas = mezclar_p
                cuestionario.mezclar_respuestas = mezclar_r
                cuestionario.permitir_revision = permitir_rev
                cuestionario.estado = nuevo_estado
                cuestionario.save()
            else:
                cuestionario = Cuestionario.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    fecha_apertura=fecha_apertura,
                    fecha_cierre=fecha_cierre,
                    tiempo_limite_minutos=tiempo_limite,
                    intentos_permitidos=intentos,
                    calificacion_maxima=calif_max,
                    calificacion_aprobacion=calif_apr,
                    mezclar_preguntas=mezclar_p,
                    mezclar_respuestas=mezclar_r,
                    permitir_revision=permitir_rev,
                    estado=nuevo_estado,
                )

            # Sincronizar reactivos asignados
            CuestionarioPregunta.objects.filter(cuestionario=cuestionario).delete()
            for orden_idx, p_id in enumerate(preguntas_ids, 1):
                p_obj = Pregunta.objects.get(id=p_id)
                CuestionarioPregunta.objects.create(
                    cuestionario=cuestionario,
                    pregunta=p_obj,
                    orden=orden_idx,
                    puntaje_asignado=p_obj.puntaje,
                )

        messages.success(request, f"Cuestionario '{cuestionario.nombre}' guardado exitosamente ({cuestionario.get_estado_display()}).")
        return redirect(f"/cuestionarios/{cuestionario.id}/editar/")

    reactivos_asignados = []
    puntaje_total = Decimal("0.00")
    if cuestionario:
        reactivos_asignados = cuestionario.cuestionario_preguntas.select_related("pregunta", "pregunta__categoria").order_by("orden")
        for cp in reactivos_asignados:
            puntaje_total += cp.puntaje_asignado or cp.pregunta.puntaje or Decimal("1.00")

    return render(request, "configurar_cuestionario.html", {
        "cuestionario": cuestionario,
        "todas_preguntas": todas_preguntas,
        "reactivos_asignados": reactivos_asignados,
        "puntaje_total": puntaje_total,
    })


# ==============================================================================
# EVALUACIÓN EN VIVO Y CALIFICACIÓN AUTOMÁTICA
# ==============================================================================

@login_required
def previsualizar_cuestionario(request, cuestionario_id):
    """
    Modo Previsualización para Docentes y Administradores:
    Permite recorrer e interactuar con el cuestionario en vivo de forma simulada,
    con opción de revelar la clave pedagógica y retroalimentación de cada reactivo,
    sin generar registros en la tabla 'intentos' ni alterar estadísticas estudiantiles.
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    es_docente_o_admin = (
        request.user.is_staff or 
        request.user.is_superuser or 
        getattr(getattr(request.user, "perfil", None), "es_docente", False) or 
        getattr(getattr(request.user, "perfil", None), "es_admin", False)
    )
    if not es_docente_o_admin:
        messages.error(request, "Acceso no autorizado: la previsualización de evaluaciones es exclusiva para el cuerpo docente.")
        return redirect("/dashboard/estudiante/")

    cuestionario_preguntas = cuestionario.cuestionario_preguntas.select_related(
        "pregunta", "pregunta__categoria"
    ).prefetch_related("pregunta__opciones").order_by("orden", "id")

    import random

    preguntas_lista = []
    for cp in cuestionario_preguntas:
        p = cp.pregunta
        opciones_lista = []
        for op in p.opciones.all().order_by("orden", "id"):
            opciones_lista.append({
                "id": op.id,
                "texto": op.texto,
                "es_correcta": op.es_correcta,
            })

        # Aplicar política de mezclar_respuestas si está activa
        if cuestionario.mezclar_respuestas:
            rng_resp = random.Random(cuestionario.id * 1000 + p.id)
            rng_resp.shuffle(opciones_lista)

        preguntas_lista.append({
            "id": p.id,
            "categoria": p.categoria.nombre if p.categoria else "General",
            "tipo": p.tipo,
            "texto_base": p.texto_base or "",
            "enunciado": p.enunciado,
            "retroalimentacion": p.retroalimentacion or "",
            "puntaje": str(p.puntaje),
            "opciones": opciones_lista,
        })

    # Aplicar política de mezclar_preguntas si está activa
    if cuestionario.mezclar_preguntas:
        rng_preg = random.Random(cuestionario.id)
        rng_preg.shuffle(preguntas_lista)

    return render(request, "cuestionario_previsualizar.html", {
        "cuestionario": cuestionario,
        "total_preguntas": len(preguntas_lista),
        "preguntas_json": json.dumps(preguntas_lista),
    })


def iniciar_evaluacion(request, cuestionario_id):
    """
    Inicia un nuevo intento de examen con validación estricta en el servidor:
    1. Verifica que la cuenta del estudiante esté activa.
    2. Verifica que el cuestionario esté disponible y en fecha válida.
    3. Verifica que no haya superado el número de intentos permitidos.
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    ahora = timezone.now()
    # Salvaguarda de rol: Redirigir a previsualización si es docente/admin para proteger estadísticas
    es_docente_o_admin = (
        request.user.is_staff or 
        request.user.is_superuser or 
        getattr(getattr(request.user, "perfil", None), "es_docente", False) or 
        getattr(getattr(request.user, "perfil", None), "es_admin", False)
    )
    if es_docente_o_admin:
        messages.info(request, "Acceso como docente: Has sido redirigido al modo de previsualización para no alterar las estadísticas estudiantiles.")
        return redirect(f"/cuestionarios/{cuestionario.id}/previsualizar/")

    # 1. Validación de cuenta
    if not request.user.is_active:
        messages.error(request, "Su cuenta se encuentra suspendida.")
        return redirect("/dashboard/estudiante/")

    # 2. Validación de disponibilidad y fechas en servidor
    if cuestionario.estado != "disponible":
        messages.error(request, "Esta evaluación no se encuentra disponible actualmente.")
        return redirect("/dashboard/estudiante/")

    if ahora < cuestionario.fecha_apertura:
        messages.error(request, f"La evaluación aún no ha iniciado. Abre el {cuestionario.fecha_apertura}.")
        return redirect("/dashboard/estudiante/")

    if ahora > cuestionario.fecha_cierre:
        messages.error(request, "El plazo para presentar este cuestionario ha expirado.")
        return redirect("/dashboard/estudiante/")

    # 3. Validación y Reanudación de Intentos
    codigo = getattr(getattr(request.user, "perfil", None), "codigo_institucional", None) or request.user.username

    # A. Verificar si el estudiante ya tiene un intento activo (en_progreso)
    intentos_activos_qs = list(
        Intento.objects.filter(
            cuestionario=cuestionario,
            participante_codigo=codigo,
            estado="en_progreso",
        ).order_by("-fecha_inicio")
    )

    if intentos_activos_qs:
        intento_activo = intentos_activos_qs[0]
        # Cerrar duplicados huérfanos si existieran
        for i_extra in intentos_activos_qs[1:]:
            i_extra.estado = "vencido"
            i_extra.fecha_fin = ahora
            i_extra.duracion_segundos = int((ahora - i_extra.fecha_inicio).total_seconds())
            i_extra.save()

        tiempo_limite_seg = cuestionario.tiempo_limite_minutos * 60
        delta_seg = int((ahora - intento_activo.fecha_inicio).total_seconds())
        ventana_gracia = 30

        if delta_seg > (tiempo_limite_seg + ventana_gracia):
            # El intento expiró por tiempo mientras el alumno estaba fuera
            intento_activo.estado = "vencido"
            intento_activo.fecha_fin = ahora
            intento_activo.duracion_segundos = delta_seg
            intento_activo.save()
            messages.warning(request, "Tu intento previo expiró por límite de tiempo y ha sido cerrado.")
            return redirect(f"/evaluacion/{intento_activo.id}/resultado/")
        else:
            # Reanudar intento activo sin consumir nuevos intentos
            messages.info(request, "Reanudando tu intento en curso. El tiempo continúa corriendo en el servidor.")
            return redirect(f"/evaluacion/{intento_activo.id}/")

    # B. Si no hay intento en progreso, validar límite de intentos completados/cerrados
    intentos_completados = Intento.objects.filter(
        cuestionario=cuestionario,
        participante_codigo=codigo,
        estado__in=["finalizado", "vencido"],
    ).count()

    if intentos_completados >= cuestionario.intentos_permitidos:
        messages.warning(
            request,
            f"Has alcanzado el límite máximo de {cuestionario.intentos_permitidos} intentos permitidos para este cuestionario."
        )
        return redirect("/dashboard/estudiante/")

    # Crear nuevo intento
    nombre_completo = request.user.get_full_name() or request.user.username
    intento = Intento.objects.create(
        cuestionario=cuestionario,
        participante_nombre=nombre_completo,
        participante_codigo=codigo,
        estado="en_progreso",
    )

    return redirect(f"/evaluacion/{intento.id}/")


@login_required
def evaluacion_en_vivo(request, intento_id):
    """Interfaz del reproductor interactivo del examen."""
    intento = get_object_or_404(Intento, id=intento_id)

    # Aislamiento de seguridad: solo el estudiante dueño o un admin puede ver el intento
    codigo_usuario = getattr(getattr(request.user, "perfil", None), "codigo_institucional", None) or request.user.username
    if intento.participante_codigo != codigo_usuario and not request.user.is_superuser:
        return HttpResponseForbidden("Acceso denegado: este intento no pertenece a su usuario.")

    if intento.estado == "finalizado":
        return redirect(f"/evaluacion/{intento.id}/resultado/")

    cuestionario = intento.cuestionario
    cuestionario_preguntas = cuestionario.cuestionario_preguntas.select_related(
        "pregunta", "pregunta__categoria"
    ).prefetch_related("pregunta__opciones").order_by("orden", "id")

    import random

    # Serializar preguntas a JSON para la navegación interactiva en JavaScript
    preguntas_lista = []
    for cp in cuestionario_preguntas:
        p = cp.pregunta
        opciones_lista = []
        for op in p.opciones.all().order_by("orden", "id"):
            opciones_lista.append({
                "id": op.id,
                "texto": op.texto,
            })

        # Aplicar política de mezclar_respuestas por intento (semilla determinista)
        if cuestionario.mezclar_respuestas:
            rng_resp = random.Random(intento.id * 1000 + p.id)
            rng_resp.shuffle(opciones_lista)

        preguntas_lista.append({
            "id": p.id,
            "enunciado": p.enunciado,
            "texto_base": p.texto_base or "",
            "categoria": p.categoria.nombre if p.categoria else "General",
            "puntaje": str(cp.puntaje_asignado or p.puntaje),
            "opciones": opciones_lista,
        })

    # Aplicar política de mezclar_preguntas por intento (semilla determinista)
    if cuestionario.mezclar_preguntas:
        rng_preg = random.Random(intento.id)
        rng_preg.shuffle(preguntas_lista)

    # Cargar respuestas previas guardadas si existen (para recuperación ante recargas)
    respuestas_previas = {
        r.pregunta_id: r.opcion_seleccionada_id
        for r in intento.respuestas.filter(opcion_seleccionada__isnull=False)
    }

    # Calcular tiempo restante exacto en el servidor
    ahora = timezone.now()
    tiempo_limite_seg = cuestionario.tiempo_limite_minutos * 60
    segundos_transcurridos = int((ahora - intento.fecha_inicio).total_seconds())
    ventana_gracia = 30

    if segundos_transcurridos > (tiempo_limite_seg + ventana_gracia):
        intento.estado = "vencido"
        intento.fecha_fin = ahora
        intento.duracion_segundos = segundos_transcurridos
        intento.save()
        messages.warning(request, "El tiempo límite para este examen ha vencido.")
        return redirect(f"/evaluacion/{intento.id}/resultado/")

    segundos_restantes = max(1, tiempo_limite_seg - segundos_transcurridos)

    return render(request, "evaluacion_en_vivo.html", {
        "intento": intento,
        "cuestionario": cuestionario,
        "total_preguntas": len(preguntas_lista),
        "preguntas_json": json.dumps(preguntas_lista),
        "respuestas_previas_json": json.dumps(respuestas_previas),
        "segundos_restantes": segundos_restantes,
    })


@login_required
def guardar_respuesta_ajax(request, intento_id):
    """
    Guarda asíncronamente (AJAX/Fetch) la selección de una pregunta para asegurar
    persistencia inmediata ante recargas, caídas de red o salidas accidentales.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    intento = get_object_or_404(Intento, id=intento_id)
    codigo_usuario = getattr(getattr(request.user, "perfil", None), "codigo_institucional", None) or request.user.username
    if intento.participante_codigo != codigo_usuario and not request.user.is_superuser:
        return JsonResponse({"error": "No autorizado"}, status=403)

    if intento.estado != "en_progreso":
        return JsonResponse({"error": "El examen ya no está activo"}, status=400)

    try:
        data = json.loads(request.body)
        pregunta_id = int(data.get("pregunta_id"))
        opcion_id = data.get("opcion_id")
        marcada = bool(data.get("marcada_para_revision", False))

        pregunta = get_object_or_404(Pregunta, id=pregunta_id)
        opcion_obj = None
        es_correcta = False
        if opcion_id:
            opcion_obj = OpcionRespuesta.objects.filter(id=int(opcion_id), pregunta=pregunta).first()
            if opcion_obj and opcion_obj.es_correcta:
                es_correcta = True

        peso = Decimal("1.00")
        cp = CuestionarioPregunta.objects.filter(cuestionario=intento.cuestionario, pregunta=pregunta).first()
        if cp:
            peso = cp.puntaje_asignado or pregunta.puntaje or Decimal("1.00")

        # Actualizar o crear registro en respuestas_intento
        RespuestaIntento.objects.update_or_create(
            intento=intento,
            pregunta=pregunta,
            defaults={
                "opcion_seleccionada": opcion_obj,
                "es_correcta": es_correcta,
                "puntaje_obtenido": peso if es_correcta else Decimal("0.00"),
                "marcada_para_revision": marcada,
            }
        )
        return JsonResponse({"status": "ok", "guardado": True})
    except Exception as e:
        return JsonResponse({"status": "error", "mensaje": str(e)}, status=400)


@login_required
def finalizar_evaluacion(request, intento_id):
    """
    Calificación automática del cuestionario en Django:
    1. Evalúa cada respuesta contra las opciones correctas en la base de datos.
    2. Suma puntaje_obtenido y puntaje_total_posible.
    3. Calcula la nota final en escala institucional (ej: 0.00 a 5.00).
    4. Determina si fue aprobado.
    5. Actualiza duración_segundos, fecha_fin y estado = 'finalizado'.
    """
    intento = get_object_or_404(Intento, id=intento_id)

    codigo_usuario = getattr(getattr(request.user, "perfil", None), "codigo_institucional", None) or request.user.username
    if intento.participante_codigo != codigo_usuario and not request.user.is_superuser:
        return HttpResponseForbidden("Acceso denegado a este intento.")

    # Si ya fue finalizado previamente, redirigir directamente al reporte de resultados
    if intento.estado == "finalizado":
        return redirect(f"/evaluacion/{intento.id}/resultado/")

    if request.method == "POST":
        respuestas_raw = request.POST.get("respuestas_json", "{}")
        try:
            respuestas_map = json.loads(respuestas_raw)
        except Exception:
            respuestas_map = {}

        cuestionario = intento.cuestionario
        cuestionario_preguntas = cuestionario.cuestionario_preguntas.select_related("pregunta").order_by("orden", "id")

        puntaje_obtenido = Decimal("0.00")
        puntaje_total_posible = Decimal("0.00")

        with transaction.atomic():
            # Limpiar respuestas previas si existieran para evitar duplicidad
            intento.respuestas.all().delete()

            for cp in cuestionario_preguntas:
                pregunta = cp.pregunta
                peso = cp.puntaje_asignado or pregunta.puntaje or Decimal("1.00")
                puntaje_total_posible += peso

                opcion_id = respuestas_map.get(str(pregunta.id)) or respuestas_map.get(pregunta.id)
                es_correcta = False
                opcion_obj = None

                if opcion_id:
                    opcion_obj = OpcionRespuesta.objects.filter(id=opcion_id, pregunta=pregunta).first()
                    if opcion_obj and opcion_obj.es_correcta:
                        es_correcta = True
                        puntaje_obtenido += peso

                # Registrar respuesta del intento
                RespuestaIntento.objects.create(
                    intento=intento,
                    pregunta=pregunta,
                    opcion_seleccionada=opcion_obj,
                    es_correcta=es_correcta,
                    puntaje_obtenido=peso if es_correcta else Decimal("0.00"),
                )

            # Normalizar calificación final según calificacion_maxima
            if puntaje_total_posible > 0:
                calificacion = (puntaje_obtenido / puntaje_total_posible) * cuestionario.calificacion_maxima
            else:
                calificacion = Decimal("0.00")

            calificacion = round(calificacion, 2)
            aprobado = calificacion >= cuestionario.calificacion_aprobacion

            # Calcular duración
            ahora = timezone.now()
            duracion_segundos = int((ahora - intento.fecha_inicio).total_seconds())

            intento.fecha_fin = ahora
            intento.duracion_segundos = max(duracion_segundos, 1)
            intento.puntaje_obtenido = puntaje_obtenido
            intento.puntaje_total_posible = puntaje_total_posible
            intento.calificacion = calificacion
            intento.aprobado = aprobado
            intento.estado = "finalizado"
            intento.save()

            # Cerrar cualquier otro intento huérfano en_progreso residual
            Intento.objects.filter(
                cuestionario=cuestionario,
                participante_codigo=codigo_usuario,
                estado="en_progreso",
            ).exclude(id=intento.id).update(
                estado="vencido",
                fecha_fin=ahora,
                duracion_segundos=1,
            )

        messages.success(request, f"¡Evaluación completada! Calificación obtenida: {calificacion} / {cuestionario.calificacion_maxima}")
        return redirect(f"/evaluacion/{intento.id}/resultado/")

    return redirect(f"/evaluacion/{intento.id}/")


@login_required
def resultado_evaluacion(request, intento_id):
    """Muestra el resultado, la calificación final calculada y la previsualización detallada de preguntas acertadas/erradas."""
    intento = get_object_or_404(Intento, id=intento_id)

    codigo_usuario = getattr(getattr(request.user, "perfil", None), "codigo_institucional", None) or request.user.username
    if intento.participante_codigo != codigo_usuario and not request.user.is_superuser:
        return HttpResponseForbidden("Acceso denegado a este reporte.")

    permitir_revision = (
        intento.cuestionario.permitir_revision
        or request.user.is_staff
        or request.user.is_superuser
    )

    # Cargar respuestas del intento con preguntas y opciones
    respuestas_qs = intento.respuestas.select_related(
        "pregunta", "pregunta__categoria", "opcion_seleccionada"
    ).prefetch_related("pregunta__opciones").all()

    detalles_respuestas = []
    total_correctas = 0
    total_incorrectas = 0
    total_sin_responder = 0
    letras = ["A", "B", "C", "D", "E"]

    if permitir_revision:
        # Mapeo de orden y puntaje según CuestionarioPregunta
        orden_dict = {
            cp.pregunta_id: (cp.orden, cp.puntaje_asignado)
            for cp in intento.cuestionario.cuestionario_preguntas.all()
        }

        respuestas_ordenadas = sorted(
            respuestas_qs,
            key=lambda r: orden_dict.get(r.pregunta_id, (9999, None))[0]
        )

        for idx, resp in enumerate(respuestas_ordenadas, start=1):
            pregunta = resp.pregunta
            orden_info = orden_dict.get(pregunta.id, (idx, None))
            peso_total = orden_info[1] or pregunta.puntaje or Decimal("1.00")

            opciones_raw = list(pregunta.opciones.all().order_by("orden", "id"))
            opcion_correcta = next((op for op in opciones_raw if op.es_correcta), None)

            if resp.opcion_seleccionada is None:
                estado_resp = "sin_responder"
                total_sin_responder += 1
            elif resp.es_correcta:
                estado_resp = "correcta"
                total_correctas += 1
            else:
                estado_resp = "incorrecta"
                total_incorrectas += 1

            opciones_procesadas = []
            for o_idx, op in enumerate(opciones_raw):
                es_sel = bool(resp.opcion_seleccionada and resp.opcion_seleccionada_id == op.id)
                opciones_procesadas.append({
                    "letra": letras[o_idx] if o_idx < len(letras) else str(o_idx + 1),
                    "id": op.id,
                    "texto": op.texto,
                    "es_correcta": op.es_correcta,
                    "es_seleccionada": es_sel,
                })

            detalles_respuestas.append({
                "numero": idx,
                "pregunta": pregunta,
                "peso_total": peso_total,
                "puntaje_obtenido": resp.puntaje_obtenido or Decimal("0.00"),
                "estado": estado_resp,
                "es_correcta": resp.es_correcta,
                "opcion_seleccionada": resp.opcion_seleccionada,
                "opcion_correcta": opcion_correcta,
                "opciones": opciones_procesadas,
                "retroalimentacion": pregunta.retroalimentacion,
            })

        total_preguntas = len(detalles_respuestas)
    else:
        # Si la revisión pedagógica está deshabilitada, se totalizan métricas sin transferir detalles
        total_correctas = respuestas_qs.filter(es_correcta=True).count()
        total_sin_responder = respuestas_qs.filter(opcion_seleccionada__isnull=True).count()
        total_incorrectas = respuestas_qs.filter(opcion_seleccionada__isnull=False, es_correcta=False).count()
        total_preguntas = respuestas_qs.count()

    porcentaje_acierto = round((total_correctas / total_preguntas * 100), 1) if total_preguntas > 0 else 0

    return render(request, "resultado_evaluacion.html", {
        "intento": intento,
        "cuestionario": intento.cuestionario,
        "detalles_respuestas": detalles_respuestas,
        "total_preguntas": total_preguntas,
        "total_correctas": total_correctas,
        "total_incorrectas": total_incorrectas,
        "total_sin_responder": total_sin_responder,
        "porcentaje_acierto": porcentaje_acierto,
        "permitir_revision": permitir_revision,
    })


# ==============================================================================
# IMPORTADOR EXCEL (PASOS 1 A 4)
# ==============================================================================

@login_required
@requiere_permiso("preguntas.importar")
def importar_preguntas(request):
    """Paso 1: subida del archivo Excel."""
    if request.method == "POST":
        form = ImportarPreguntasForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data["archivo"]
            cuestionario_obj = form.cleaned_data.get("cuestionario")
            cuestionario_id = cuestionario_obj.id if cuestionario_obj else None

            # Limpiamos importación previa huérfana si la hubiera
            previa = request.session.pop("importacion_pendiente", None)
            if previa and default_storage.exists(previa.get("ruta", "")):
                default_storage.delete(previa["ruta"])

            ruta_relativa = f"{CARPETA_TEMPORAL}/{uuid.uuid4().hex}.xlsx"
            ruta_guardada = default_storage.save(ruta_relativa, archivo)

            request.session["importacion_pendiente"] = {
                "ruta": ruta_guardada,
                "nombre_archivo": archivo.name,
                "cuestionario_id": cuestionario_id,
                "cuestionario_nombre": cuestionario_obj.nombre if cuestionario_obj else None,
            }

            return redirect("preguntas:previsualizar")
    else:
        form = ImportarPreguntasForm()

    pendiente = request.session.get("importacion_pendiente")
    return render(request, "preguntas/importar_preguntas.html", {
        "form": form,
        "pendiente": pendiente,
    })


@login_required
@requiere_permiso("preguntas.importar")
def previsualizar_importacion(request):
    """Paso 2 y 3: previsualización, auditoría y corrección en caliente de preguntas."""
    pendiente = request.session.get("importacion_pendiente")
    if not pendiente or not default_storage.exists(pendiente.get("ruta", "")):
        messages.warning(request, "No hay ningún archivo cargado pendiente por validar.")
        return redirect("preguntas:importar")

    ruta_absoluta = default_storage.path(pendiente["ruta"])
    resultado = procesar_archivo(
        ruta_absoluta, pendiente["nombre_archivo"], commit=False,
    )

    cuestionario_obj = None
    if pendiente.get("cuestionario_id"):
        cuestionario_obj = Cuestionario.objects.filter(id=pendiente["cuestionario_id"]).first()

    return render(request, "preguntas/previsualizar_importacion.html", {
        "resultado": resultado,
        "cuestionario": cuestionario_obj,
    })


@login_required
@requiere_permiso("preguntas.importar")
def corregir_fila_importacion(request):
    """Permite corregir directamente los datos de una fila errónea desde la vista web."""
    if request.method != "POST":
        return redirect("preguntas:importar")

    pendiente = request.session.get("importacion_pendiente")
    if not pendiente or not default_storage.exists(pendiente.get("ruta", "")):
        messages.error(request, "No hay ninguna importación en curso.")
        return redirect("preguntas:importar")

    try:
        fila_excel = int(request.POST.get("fila_excel", 0))
    except (ValueError, TypeError):
        messages.error(request, "Número de fila inválido.")
        return redirect("preguntas:previsualizar")

    if fila_excel < 2:
        messages.error(request, "La fila a corregir no es válida.")
        return redirect("preguntas:previsualizar")

    tipo = request.POST.get("tipo", "").strip().upper()
    if not tipo or tipo not in ("MULTIPLE", "V_F"):
        messages.error(
            request,
            f"Fila #{fila_excel}: Debes seleccionar obligatoriamente un tipo válido (MULTIPLE o V_F).",
        )
        return redirect("preguntas:previsualizar")

    nuevos_valores = {
        "categoria": request.POST.get("categoria", "").strip(),
        "tipo": tipo,
        "texto_base": request.POST.get("texto_base", "").strip(),
        "pregunta": request.POST.get("pregunta", "").strip(),
        "opcion_a": request.POST.get("opcion_a", "").strip(),
        "opcion_b": request.POST.get("opcion_b", "").strip(),
        "opcion_c": request.POST.get("opcion_c", "").strip(),
        "opcion_d": request.POST.get("opcion_d", "").strip(),
        "respuesta_correcta": request.POST.get("respuesta_correcta", "").strip().upper(),
        "retroalimentacion": request.POST.get("retroalimentacion", "").strip(),
        "puntaje": request.POST.get("puntaje", "1.0").strip(),
    }

    ruta_absoluta = default_storage.path(pendiente["ruta"])
    actualizar_fila_excel(ruta_absoluta, fila_excel, nuevos_valores)

    # Validamos cómo quedó
    fila_evaluada = _validar_fila(nuevos_valores)
    if fila_evaluada.estado == "valida":
        messages.success(request, f"¡Fila #{fila_excel} corregida con éxito! Ahora es válida para importar.")
    else:
        messages.warning(
            request,
            f"Fila #{fila_excel} actualizada, pero aún tiene observaciones: {', '.join(fila_evaluada.errores)}",
        )

    return redirect("preguntas:previsualizar")


@login_required
@requiere_permiso("preguntas.importar")
def confirmar_importacion(request):
    """Paso 4: confirmación y guardado en base de datos dentro de transacción."""
    if request.method != "POST":
        return redirect("preguntas:importar")

    pendiente = request.session.get("importacion_pendiente")
    if not pendiente or not default_storage.exists(pendiente.get("ruta", "")):
        messages.error(request, "No hay una importación pendiente por confirmar.")
        return redirect("preguntas:importar")

    ruta_absoluta = default_storage.path(pendiente["ruta"])
    resultado = procesar_archivo(
        ruta_absoluta, pendiente["nombre_archivo"], commit=True,
        cuestionario_id=pendiente.get("cuestionario_id"),
    )

    default_storage.delete(pendiente["ruta"])
    del request.session["importacion_pendiente"]

    messages.success(
        request,
        f"Importación #{resultado.importacion_id}: "
        f"{len(resultado.validas)} preguntas guardadas, "
        f"{len(resultado.duplicadas)} duplicadas, "
        f"{len(resultado.con_error)} con error.",
    )
    return render(request, "preguntas/resultado_importacion.html", {"resultado": resultado})


@login_required
def cancelar_importacion(request):
    pendiente = request.session.pop("importacion_pendiente", None)
    if pendiente and default_storage.exists(pendiente.get("ruta", "")):
        default_storage.delete(pendiente["ruta"])
    messages.info(request, "Se ha cancelado la importación y liberado el archivo temporal.")
    return redirect("preguntas:importar")


# ==============================================================================
# GESTIÓN Y AUDITORÍA DE INTENTOS DE ESTUDIANTES (DOCENTE / ADMIN)
# ==============================================================================

@login_required
@requiere_permiso("cuestionarios.gestionar")
def cuestionario_intentos(request, cuestionario_id):
    """
    Panel para Docentes y Administradores para auditar y gestionar
    todos los intentos presentados por los estudiantes en un cuestionario.
    Agrupa por estudiante único (1 fila por alumno con acordeón de intentos)
    para evitar saturación de filas repetidas en cuestionarios con múltiples intentos.
    """
    from collections import OrderedDict
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    q = request.GET.get("q", "").strip()
    estado_filtro = request.GET.get("estado", "").strip()
    vista_tab = request.GET.get("vista", "estudiantes").strip()

    intentos_qs = cuestionario.intentos.all().order_by("-fecha_inicio")

    if q:
        intentos_qs = intentos_qs.filter(
            Q(participante_nombre__icontains=q) | Q(participante_codigo__icontains=q)
        )

    if estado_filtro:
        intentos_qs = intentos_qs.filter(estado=estado_filtro)

    # 1. Agrupar intentos por estudiante único
    estudiantes_dict = OrderedDict()
    for it in intentos_qs:
        cod = it.participante_codigo
        if cod not in estudiantes_dict:
            estudiantes_dict[cod] = {
                "codigo": cod,
                "nombre": it.participante_nombre,
                "intentos": [],
                "mejor_calificacion": None,
                "aprobado": False,
                "tiene_activo": False,
                "ultimo_intento": it,
            }
        estudiantes_dict[cod]["intentos"].append(it)
        if it.estado == "en_progreso":
            estudiantes_dict[cod]["tiene_activo"] = True

    # 2. Calcular nota definitiva institucional (la nota más alta obtenida)
    estudiantes_agrupados = []
    notas_definitivas = []
    estudiantes_aprobados_count = 0

    for cod, datos in estudiantes_dict.items():
        califs = [
            i.calificacion for i in datos["intentos"]
            if i.estado in ["finalizado", "vencido"] and i.calificacion is not None
        ]
        if califs:
            mejor = max(califs)
            datos["mejor_calificacion"] = mejor
            datos["aprobado"] = mejor >= cuestionario.calificacion_aprobacion
            notas_definitivas.append(mejor)
            if datos["aprobado"]:
                estudiantes_aprobados_count += 1
        else:
            datos["mejor_calificacion"] = None
            datos["aprobado"] = False
        
        datos["total_intentos"] = len(datos["intentos"])
        estudiantes_agrupados.append(datos)

    # 3. Métricas consolidadas
    total_estudiantes = len(estudiantes_agrupados)
    estudiantes_reprobados_count = total_estudiantes - estudiantes_aprobados_count
    tasa_aprobacion_estudiantes = (
        round((estudiantes_aprobados_count / total_estudiantes * 100), 1)
        if total_estudiantes > 0 else 0
    )
    promedio_definitivo = (
        round(sum(notas_definitivas) / len(notas_definitivas), 2)
        if notas_definitivas else Decimal("0.00")
    )

    todos_los_intentos = cuestionario.intentos.all()
    total_intentos_registrados = todos_los_intentos.count()

    return render(request, "cuestionario_intentos.html", {
        "cuestionario": cuestionario,
        "estudiantes_agrupados": estudiantes_agrupados,
        "intentos": intentos_qs,
        "total_estudiantes": total_estudiantes,
        "estudiantes_aprobados_count": estudiantes_aprobados_count,
        "estudiantes_reprobados_count": estudiantes_reprobados_count,
        "tasa_aprobacion": tasa_aprobacion_estudiantes,
        "promedio_calif": promedio_definitivo,
        "total_intentos_registrados": total_intentos_registrados,
        "q": q,
        "estado_filtro": estado_filtro,
        "vista_tab": vista_tab,
        "active_tab": "cuestionarios",
    })


@login_required
@requiere_permiso("cuestionarios.gestionar")
def reiniciar_estudiante_cuestionario(request, cuestionario_id, codigo_estudiante):
    """
    Reinicia y purga todos los intentos de un estudiante en un cuestionario específico,
    restaurando su cupo íntegro de intentos permitidos de inmediato.
    """
    if request.method != "POST":
        return redirect(f"/cuestionarios/{cuestionario_id}/intentos/")

    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    with transaction.atomic():
        eliminados, _ = Intento.objects.filter(
            cuestionario=cuestionario,
            participante_codigo=codigo_estudiante
        ).delete()

    messages.success(
        request,
        f"Se han reiniciado los {eliminados} intentos del estudiante ({codigo_estudiante}). Su cupo ha quedado totalmente restaurado."
    )
    return redirect(f"/cuestionarios/{cuestionario_id}/intentos/")


@login_required
@requiere_permiso("cuestionarios.gestionar")
def reiniciar_intento(request, intento_id):
    """
    Permite al Docente o Administrador anular/reiniciar el intento de un estudiante
    ante contingencias justificadas (caída de red, fuerza mayor), restaurando su cupo.
    """
    if request.method != "POST":
        return redirect("/cuestionarios/")

    intento = get_object_or_404(Intento, id=intento_id)
    cuestionario_id = intento.cuestionario_id
    codigo = intento.participante_codigo
    nombre = intento.participante_nombre

    with transaction.atomic():
        # Al eliminar el intento, MariaDB borra en cascada sus respuestas_intento
        intento.delete()

    messages.success(
        request,
        f"Se ha reiniciado con éxito el intento de {nombre} ({codigo}). El estudiante ahora cuenta con su cupo restaurado para presentar nuevamente la prueba."
    )
    return redirect(f"/cuestionarios/{cuestionario_id}/intentos/")


@login_required
@requiere_permiso("cuestionarios.gestionar")
def exportar_intentos_csv(request, cuestionario_id):
    """
    Exporta la planilla completa de calificaciones e intentos en CSV con codificación
    UTF-8 con BOM para visualización perfecta e inmediata en Microsoft Excel.
    """
    import csv
    from django.utils.text import slugify

    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    intentos = cuestionario.intentos.all().order_by("participante_codigo", "-fecha_inicio")

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    nombre_archivo = f"sabana_notas_cuestionario_{cuestionario.id}_{slugify(cuestionario.nombre)}.csv"
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'

    writer = csv.writer(response)
    # Cabecera oficial
    writer.writerow([
        "ID Intento",
        "Código Estudiante",
        "Nombre Completo",
        "Fecha Inicio",
        "Fecha Entrega",
        "Duración (Segundos)",
        "Puntaje Obtenido",
        "Puntaje Posible",
        "Calificación",
        "Escala Máxima",
        "Mínimo Aprobación",
        "Estado Intento",
        "Dictamen"
    ])

    for i in intentos:
        inicio_str = i.fecha_inicio.strftime("%Y-%m-%d %H:%M:%S") if i.fecha_inicio else ""
        fin_str = i.fecha_fin.strftime("%Y-%m-%d %H:%M:%S") if i.fecha_fin else ""
        dictamen_str = "Aprobado" if i.aprobado else ("Reprobado" if i.estado == "finalizado" else "Pendiente")

        writer.writerow([
            i.id,
            i.participante_codigo,
            i.participante_nombre,
            inicio_str,
            fin_str,
            i.duracion_segundos or "",
            str(i.puntaje_obtenido or "0.00"),
            str(i.puntaje_total_posible or "0.00"),
            str(i.calificacion or "0.00"),
            str(cuestionario.calificacion_maxima),
            str(cuestionario.calificacion_aprobacion),
            i.estado,
            dictamen_str
        ])

    return response
