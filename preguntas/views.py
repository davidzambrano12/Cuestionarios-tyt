import json
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
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
from .services.importador_excel import calcular_huella, procesar_archivo

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
    """Lista de cuestionarios para administración y edición."""
    cuestionarios = Cuestionario.objects.all().order_by("-id")
    return render(request, "admin_dashboard.html", {
        "cuestionarios_recientes": cuestionarios,
        "cuestionarios_count": cuestionarios.count(),
    })


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
        intentos = int(request.POST.get("intentos_permitidos", 2))
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
def iniciar_evaluacion(request, cuestionario_id):
    """
    Inicia un nuevo intento de examen con validación estricta en el servidor:
    1. Verifica que la cuenta del estudiante esté activa.
    2. Verifica que el cuestionario esté disponible y en fecha válida.
    3. Verifica que no haya superado el número de intentos permitidos.
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    ahora = timezone.now()

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

    # 3. Validación de intentos permitidos
    codigo = getattr(getattr(request.user, "perfil", None), "codigo_institucional", None) or request.user.username
    intentos_previos = Intento.objects.filter(
        cuestionario=cuestionario,
        participante_codigo=codigo,
    ).count()

    if intentos_previos >= cuestionario.intentos_permitidos:
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
    ).prefetch_related("pregunta__opciones").order_by("orden")

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
        
        preguntas_lista.append({
            "id": p.id,
            "enunciado": p.enunciado,
            "texto_base": p.texto_base or "",
            "categoria": p.categoria.nombre if p.categoria else "General",
            "puntaje": str(cp.puntaje_asignado or p.puntaje),
            "opciones": opciones_lista,
        })

    return render(request, "evaluacion_en_vivo.html", {
        "intento": intento,
        "cuestionario": cuestionario,
        "total_preguntas": len(preguntas_lista),
        "preguntas_json": json.dumps(preguntas_lista),
    })


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

    if request.method == "POST":
        respuestas_raw = request.POST.get("respuestas_json", "{}")
        try:
            respuestas_map = json.loads(respuestas_raw)
        except Exception:
            respuestas_map = {}

        cuestionario = intento.cuestionario
        cuestionario_preguntas = cuestionario.cuestionario_preguntas.select_related("pregunta").all()

        puntaje_obtenido = Decimal("0.00")
        puntaje_total_posible = Decimal("0.00")

        with transaction.atomic():
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

        messages.success(request, f"¡Evaluación completada! Calificación obtenida: {calificacion} / {cuestionario.calificacion_maxima}")
        return redirect(f"/evaluacion/{intento.id}/resultado/")

    return redirect(f"/evaluacion/{intento.id}/")


@login_required
def resultado_evaluacion(request, intento_id):
    """Muestra el resultado y la calificación final calculada por Django."""
    intento = get_object_or_404(Intento, id=intento_id)

    codigo_usuario = getattr(getattr(request.user, "perfil", None), "codigo_institucional", None) or request.user.username
    if intento.participante_codigo != codigo_usuario and not request.user.is_superuser:
        return HttpResponseForbidden("Acceso denegado a este reporte.")

    return render(request, "resultado_evaluacion.html", {"intento": intento})


# ==============================================================================
# IMPORTADOR EXCEL (PASOS 1 A 4)
# ==============================================================================

@login_required
@requiere_permiso("preguntas.importar")
def importar_preguntas(request):
    """Paso 1: subida y validación del archivo Excel."""
    if request.method == "POST":
        form = ImportarPreguntasForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data["archivo"]
            cuestionario_obj = form.cleaned_data.get("cuestionario")
            cuestionario_id = cuestionario_obj.id if cuestionario_obj else None

            ruta_relativa = f"{CARPETA_TEMPORAL}/{uuid.uuid4().hex}.xlsx"
            ruta_guardada = default_storage.save(ruta_relativa, archivo)
            ruta_absoluta = default_storage.path(ruta_guardada)

            resultado = procesar_archivo(
                ruta_absoluta, archivo.name, commit=False,
            )

            request.session["importacion_pendiente"] = {
                "ruta": ruta_guardada,
                "nombre_archivo": archivo.name,
                "cuestionario_id": cuestionario_id,
                "cuestionario_nombre": cuestionario_obj.nombre if cuestionario_obj else None,
            }

            return render(request, "preguntas/previsualizar_importacion.html", {
                "resultado": resultado,
                "cuestionario": cuestionario_obj,
            })
    else:
        form = ImportarPreguntasForm()

    return render(request, "preguntas/importar_preguntas.html", {"form": form})


@login_required
@requiere_permiso("preguntas.importar")
def confirmar_importacion(request):
    """Paso 2: confirmación y guardado en base de datos dentro de transacción."""
    if request.method != "POST":
        return redirect("preguntas:importar")

    pendiente = request.session.get("importacion_pendiente")
    if not pendiente:
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
    if pendiente:
        default_storage.delete(pendiente["ruta"])
    return redirect("preguntas:importar")
