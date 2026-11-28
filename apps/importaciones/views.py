"""Módulo B: importación de preguntas desde Excel (subir, previsualizar, corregir, confirmar)."""
import uuid
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.urls import reverse

from apps.core.decorators import requiere_permiso
from apps.importaciones.forms import ImportarPreguntasForm
from apps.importaciones.models import ImportacionPendiente
from apps.cuestionarios.models import Cuestionario
from apps.importaciones.services import COLUMNAS, _validar_fila, actualizar_fila_excel, procesar_archivo

CLAVE_SESION = "importacion_pendiente"


def _pendiente(request, *, bloquear=False):
    """Recupera el archivo compartido, restringido al usuario y a la sesión."""
    datos = request.session.get(CLAVE_SESION)
    if not datos:
        return None
    # Conserva las cargas anteriores cuando su archivo local aún está disponible.
    if "ruta" in datos:
        ruta = datos["ruta"]
        if not default_storage.exists(ruta):
            request.session.pop(CLAVE_SESION, None)
            return None
        with default_storage.open(ruta, "rb") as archivo:
            pendiente, _ = ImportacionPendiente.objects.get_or_create(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"{request.user.pk}:{ruta}"),
                defaults={
                    "usuario": request.user, "archivo": archivo.read(),
                    "nombre_archivo": datos["nombre_archivo"],
                    "cuestionario_id": datos.get("cuestionario_id"),
                    "excluidas": datos.get("excluidas", []),
                    "vence": request.session.get_expiry_date(),
                },
            )
        datos = {"id": str(pendiente.pk)}
        request.session[CLAVE_SESION] = datos
    try:
        identificador = uuid.UUID(str(datos.get("id", "")))
    except ValueError:
        request.session.pop(CLAVE_SESION, None)
        return None
    consulta = ImportacionPendiente.objects.filter(
        pk=identificador, usuario=request.user, vence__gt=timezone.now(),
    )
    if bloquear:
        consulta = consulta.select_for_update()
    return consulta.first()


def _excluidas(pendiente) -> frozenset[int]:
    return frozenset(pendiente.excluidas)


def _volver_a_fila(fila_excel: int):
    """Regresa a la revisión, desplazada hasta la tarjeta de esa fila."""
    return redirect(f"{reverse('importaciones:previsualizar')}#fila-{fila_excel}")


def _fila_del_post(request) -> int:
    try:
        return int(request.POST.get("fila_excel", 0))
    except (ValueError, TypeError):
        return 0


def _descartar_pendiente(request):
    pendiente = _pendiente(request, bloquear=True)
    if pendiente:
        pendiente.delete()
    request.session.pop(CLAVE_SESION, None)


@login_required
@requiere_permiso("preguntas.importar")
@transaction.atomic
def importar_preguntas(request):
    """Paso 1: subida del archivo."""
    if request.method == "POST":
        form = ImportarPreguntasForm(request.POST, request.FILES, usuario=request.user)
        if form.is_valid():
            archivo = form.cleaned_data["archivo"]
            cuestionario = form.cleaned_data.get("cuestionario")
            _descartar_pendiente(request)
            ImportacionPendiente.objects.filter(vence__lte=timezone.now()).delete()
            pendiente = ImportacionPendiente.objects.create(
                usuario=request.user, archivo=archivo.read(), nombre_archivo=archivo.name,
                cuestionario=cuestionario, vence=request.session.get_expiry_date(),
            )
            request.session[CLAVE_SESION] = {"id": str(pendiente.pk)}
            return redirect("importaciones:previsualizar")
    else:
        form = ImportarPreguntasForm(usuario=request.user)

    return render(request, "importaciones/importar.html", {
        "form": form,
        "pendiente": _pendiente(request),
    })


@login_required
@requiere_permiso("preguntas.importar")
def previsualizar_importacion(request):
    """Pasos 2 y 3: validación en memoria (dry-run) con el reporte por fila."""
    pendiente = _pendiente(request)
    if not pendiente:
        messages.warning(request, "No hay ningún archivo cargado pendiente por validar.")
        return redirect("importaciones:importar")

    resultado = procesar_archivo(
        BytesIO(bytes(pendiente.archivo)), pendiente.nombre_archivo,
        commit=False, excluidas=_excluidas(pendiente),
    )
    cuestionario = None
    if pendiente.cuestionario_id:
        cuestionario = Cuestionario.objects.filter(id=pendiente.cuestionario_id).first()
    return render(request, "importaciones/previsualizar.html", {
        "resultado": resultado,
        "cuestionario": cuestionario,
    })


@login_required
@requiere_permiso("preguntas.importar")
@transaction.atomic
def corregir_fila_importacion(request):
    """Guarda las correcciones del Excel en la base de datos compartida."""
    if request.method != "POST":
        return redirect("importaciones:importar")
    pendiente = _pendiente(request, bloquear=True)
    if not pendiente:
        messages.error(request, "No hay ninguna importación en curso.")
        return redirect("importaciones:importar")

    fila_excel = _fila_del_post(request)
    if fila_excel < 2:
        messages.error(request, "La fila a corregir no es válida.")
        return redirect("importaciones:previsualizar")

    tipo = request.POST.get("tipo", "").strip().upper()
    if tipo not in ("MULTIPLE", "V_F"):
        messages.error(request, f"Fila #{fila_excel}: Debes seleccionar obligatoriamente un tipo válido (MULTIPLE o V_F).")
        return _volver_a_fila(fila_excel)

    nuevos_valores = {columna: request.POST.get(columna, "").strip() for columna in COLUMNAS}
    nuevos_valores["tipo"] = tipo
    nuevos_valores["respuesta_correcta"] = nuevos_valores["respuesta_correcta"].upper()
    nuevos_valores["puntaje"] = nuevos_valores["puntaje"] or "1.0"

    corregido = BytesIO()
    actualizar_fila_excel(BytesIO(bytes(pendiente.archivo)), fila_excel, nuevos_valores, destino=corregido)
    pendiente.archivo = corregido.getvalue()
    pendiente.save(update_fields=["archivo"])
    fila = _validar_fila(nuevos_valores)
    if fila.estado == "valida":
        messages.success(request, f"Fila {fila_excel} guardada. Ya es válida para importar.")
    else:
        messages.warning(request, f"Fila {fila_excel} actualizada, pero aún tiene observaciones: {', '.join(fila.errores)}")
    return _volver_a_fila(fila_excel)


@login_required
@requiere_permiso("preguntas.importar")
@transaction.atomic
def excluir_fila_importacion(request):
    """Marca una fila para no importarla, o la vuelve a incluir."""
    if request.method != "POST":
        return redirect("importaciones:previsualizar")
    pendiente = _pendiente(request, bloquear=True)
    if not pendiente:
        messages.error(request, "No hay ninguna importación en curso.")
        return redirect("importaciones:importar")

    fila_excel = _fila_del_post(request)
    if fila_excel < 2:
        messages.error(request, "La fila indicada no es válida.")
        return redirect("importaciones:previsualizar")

    excluidas = set(pendiente.excluidas)
    if request.POST.get("accion") == "incluir":
        excluidas.discard(fila_excel)
        messages.info(request, f"La fila {fila_excel} se volvió a incluir en la importación.")
    else:
        excluidas.add(fila_excel)
        messages.info(request, f"La fila {fila_excel} no se importará.")
    pendiente.excluidas = sorted(excluidas)
    pendiente.save(update_fields=["excluidas"])
    return _volver_a_fila(fila_excel)


@login_required
@requiere_permiso("preguntas.importar")
@transaction.atomic
def confirmar_importacion(request):
    """Paso 4: guarda las filas válidas en una transacción y registra la bitácora."""
    if request.method != "POST":
        return redirect("importaciones:importar")
    pendiente = _pendiente(request, bloquear=True)
    if not pendiente:
        messages.error(request, "No hay una importación pendiente por confirmar.")
        return redirect("importaciones:importar")

    resultado = procesar_archivo(
        BytesIO(bytes(pendiente.archivo)), pendiente.nombre_archivo,
        commit=True, cuestionario_id=pendiente.cuestionario_id,
        excluidas=_excluidas(pendiente),
    )
    pendiente.delete()
    request.session.pop(CLAVE_SESION, None)

    messages.success(
        request,
        f"Importación #{resultado.importacion_id}: "
        f"{len(resultado.validas)} preguntas guardadas, "
        f"{len(resultado.duplicadas)} duplicadas, "
        f"{len(resultado.con_error)} con error"
        + (f", {len(resultado.excluidas)} excluidas." if resultado.excluidas else "."),
    )
    return render(request, "importaciones/resultado.html", {"resultado": resultado})


@login_required
@transaction.atomic
def cancelar_importacion(request):
    _descartar_pendiente(request)
    messages.info(request, "Se ha cancelado la importación y liberado el archivo temporal.")
    return redirect("importaciones:importar")
