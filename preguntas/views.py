import uuid

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.shortcuts import redirect, render

from .forms import ImportarPreguntasForm
from .services.importador_excel import procesar_archivo

CARPETA_TEMPORAL = "importaciones_tmp"


def importar_preguntas(request):
    """Paso 1: el usuario sube el Excel. Se valida (sin guardar nada en la
    base de datos todavía) y se muestra la previsualización."""
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

            # Se guarda en sesión solo lo necesario para confirmar después;
            # el archivo real queda en disco (carpeta temporal) hasta confirmar o cancelar.
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


def confirmar_importacion(request):
    """Paso 2: el usuario confirma -> ahora sí se guarda en la base de datos."""
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


def cancelar_importacion(request):
    pendiente = request.session.pop("importacion_pendiente", None)
    if pendiente:
        default_storage.delete(pendiente["ruta"])
    return redirect("preguntas:importar")
