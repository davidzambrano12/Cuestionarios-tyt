"""Módulo B: importación de preguntas desde Excel (subir, previsualizar, corregir, confirmar)."""
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.core.decorators import requiere_permiso
from apps.importaciones.forms import ImportarPreguntasForm
from apps.cuestionarios.models import Cuestionario
from apps.importaciones.services import COLUMNAS, _validar_fila, actualizar_fila_excel, procesar_archivo

CARPETA_TEMPORAL = "importaciones_tmp"
CLAVE_SESION = "importacion_pendiente"


def _pendiente(request):
    """Importación en curso guardada en sesión, solo si su archivo sigue existiendo."""
    pendiente = request.session.get(CLAVE_SESION)
    if pendiente and default_storage.exists(pendiente.get("ruta", "")):
        return pendiente
    return None


def _excluidas(pendiente) -> frozenset[int]:
    return frozenset(pendiente.get("excluidas", []))


def _volver_a_fila(fila_excel: int):
    """Regresa a la revisión, desplazada hasta la tarjeta de esa fila."""
    return redirect(f"{reverse('importaciones:previsualizar')}#fila-{fila_excel}")


def _fila_del_post(request) -> int:
    try:
        return int(request.POST.get("fila_excel", 0))
    except (ValueError, TypeError):
        return 0


def _descartar_pendiente(request):
    pendiente = request.session.pop(CLAVE_SESION, None)
    if pendiente and default_storage.exists(pendiente.get("ruta", "")):
        default_storage.delete(pendiente["ruta"])


@login_required
@requiere_permiso("preguntas.importar")
def importar_preguntas(request):
    """Paso 1: subida del archivo."""
    if request.method == "POST":
        form = ImportarPreguntasForm(request.POST, request.FILES, usuario=request.user)
        if form.is_valid():
            archivo = form.cleaned_data["archivo"]
            cuestionario = form.cleaned_data.get("cuestionario")
            _descartar_pendiente(request)
            ruta = default_storage.save(f"{CARPETA_TEMPORAL}/{uuid.uuid4().hex}.xlsx", archivo)
            request.session[CLAVE_SESION] = {
                "ruta": ruta,
                "nombre_archivo": archivo.name,
                "cuestionario_id": cuestionario.id if cuestionario else None,
                "cuestionario_nombre": cuestionario.nombre if cuestionario else None,
            }
            return redirect("importaciones:previsualizar")
    else:
        form = ImportarPreguntasForm(usuario=request.user)

    return render(request, "importaciones/importar.html", {
        "form": form,
        "pendiente": request.session.get(CLAVE_SESION),
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
        default_storage.path(pendiente["ruta"]), pendiente["nombre_archivo"],
        commit=False, excluidas=_excluidas(pendiente),
    )
    cuestionario = None
    if pendiente.get("cuestionario_id"):
        cuestionario = Cuestionario.objects.filter(id=pendiente["cuestionario_id"]).first()
    return render(request, "importaciones/previsualizar.html", {
        "resultado": resultado,
        "cuestionario": cuestionario,
    })


@login_required
@requiere_permiso("preguntas.importar")
def corregir_fila_importacion(request):
    """Corrige en el archivo temporal los datos de una fila con error."""
    if request.method != "POST":
        return redirect("importaciones:importar")
    pendiente = _pendiente(request)
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

    actualizar_fila_excel(default_storage.path(pendiente["ruta"]), fila_excel, nuevos_valores)
    fila = _validar_fila(nuevos_valores)
    if fila.estado == "valida":
        messages.success(request, f"Fila {fila_excel} guardada. Ya es válida para importar.")
    else:
        messages.warning(request, f"Fila {fila_excel} actualizada, pero aún tiene observaciones: {', '.join(fila.errores)}")
    return _volver_a_fila(fila_excel)


@login_required
@requiere_permiso("preguntas.importar")
def excluir_fila_importacion(request):
    """Marca una fila para no importarla, o la vuelve a incluir."""
    if request.method != "POST":
        return redirect("importaciones:previsualizar")
    pendiente = _pendiente(request)
    if not pendiente:
        messages.error(request, "No hay ninguna importación en curso.")
        return redirect("importaciones:importar")

    fila_excel = _fila_del_post(request)
    if fila_excel < 2:
        messages.error(request, "La fila indicada no es válida.")
        return redirect("importaciones:previsualizar")

    excluidas = set(pendiente.get("excluidas", []))
    if request.POST.get("accion") == "incluir":
        excluidas.discard(fila_excel)
        messages.info(request, f"La fila {fila_excel} se volvió a incluir en la importación.")
    else:
        excluidas.add(fila_excel)
        messages.info(request, f"La fila {fila_excel} no se importará.")
    pendiente["excluidas"] = sorted(excluidas)
    request.session[CLAVE_SESION] = pendiente
    return _volver_a_fila(fila_excel)


@login_required
@requiere_permiso("preguntas.importar")
def confirmar_importacion(request):
    """Paso 4: guarda las filas válidas en una transacción y registra la bitácora."""
    if request.method != "POST":
        return redirect("importaciones:importar")
    pendiente = _pendiente(request)
    if not pendiente:
        messages.error(request, "No hay una importación pendiente por confirmar.")
        return redirect("importaciones:importar")

    resultado = procesar_archivo(
        default_storage.path(pendiente["ruta"]), pendiente["nombre_archivo"],
        commit=True, cuestionario_id=pendiente.get("cuestionario_id"),
        excluidas=_excluidas(pendiente),
    )
    _descartar_pendiente(request)

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
def cancelar_importacion(request):
    _descartar_pendiente(request)
    messages.info(request, "Se ha cancelado la importación y liberado el archivo temporal.")
    return redirect("importaciones:importar")
