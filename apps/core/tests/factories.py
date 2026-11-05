"""
Utilidades compartidas por las pruebas: crean usuarios por rol y
cuestionarios listos para presentar, sin depender de datos de la BD real.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

from apps.core.models import PerfilUsuario, Rol
from apps.banco_preguntas.models import Categoria, OpcionRespuesta, Pregunta
from apps.cuestionarios.models import Cuestionario, CuestionarioPregunta
from apps.evaluaciones.models import Intento

CLAVE = "Clave-Segura-2026"


def sembrar_roles():
    """
    Crea permisos, roles y usuarios base con el mismo seed del proyecto y
    descarta su contenido de demostración, para que cada prueba parta de un
    banco de preguntas y cuestionarios vacío.
    """
    call_command("seed_data", stdout=_Silencio())
    Intento.objects.all().delete()
    CuestionarioPregunta.objects.all().delete()
    Cuestionario.objects.all().delete()
    OpcionRespuesta.objects.all().delete()
    Pregunta.objects.all().delete()
    Categoria.objects.all().delete()


class _Silencio:
    def write(self, *_args, **_kwargs):
        pass

    def flush(self):
        pass


def crear_usuario(username, rol_codigo, codigo=None, **extra):
    user = User.objects.create_user(
        username=username,
        password=CLAVE,
        first_name=extra.pop("first_name", username.capitalize()),
        last_name=extra.pop("last_name", "Prueba"),
        email=extra.pop("email", f"{username}@uniputumayo.edu.co"),
        **extra,
    )
    PerfilUsuario.objects.update_or_create(
        user=user,
        defaults={
            "rol": Rol.objects.get(codigo=rol_codigo),
            "codigo_institucional": codigo or f"COD-{username.upper()}",
        },
    )
    return user


def crear_pregunta(categoria, enunciado, correcta=0, puntaje=Decimal("1.00")):
    pregunta = Pregunta.objects.create(
        categoria=categoria,
        tipo=Pregunta.TIPO_MULTIPLE,
        enunciado=enunciado,
        puntaje=puntaje,
        retroalimentacion=f"Explicación de {enunciado}",
        activa=True,
    )
    for idx, letra in enumerate("ABCD"):
        OpcionRespuesta.objects.create(
            pregunta=pregunta, texto=f"{enunciado} opción {letra}",
            es_correcta=(idx == correcta), orden=idx + 1,
        )
    return pregunta


def crear_cuestionario(num_preguntas=2, **campos):
    """Cuestionario disponible, abierto ahora, con `num_preguntas` de 1 punto."""
    ahora = timezone.now()
    datos = {
        "nombre": "Simulacro de prueba",
        "fecha_apertura": ahora - timedelta(hours=1),
        "fecha_cierre": ahora + timedelta(days=1),
        "tiempo_limite_minutos": 60,
        "intentos_permitidos": 2,
        "calificacion_maxima": Decimal("5.00"),
        "calificacion_aprobacion": Decimal("3.00"),
        "permitir_revision": True,
        "estado": "disponible",
        "visibilidad": "institucional",  # cualquier estudiante puede presentarlo
    }
    datos.update(campos)
    cuestionario = Cuestionario.objects.create(**datos)
    categoria, _ = Categoria.objects.get_or_create(nombre="Razonamiento Cuantitativo")
    for orden in range(1, num_preguntas + 1):
        pregunta = crear_pregunta(categoria, f"Pregunta {cuestionario.id}-{orden}")
        CuestionarioPregunta.objects.create(
            cuestionario=cuestionario, pregunta=pregunta,
            orden=orden, puntaje_asignado=pregunta.puntaje,
        )
    return cuestionario


def respuestas_correctas(cuestionario, cuantas=None):
    """Mapa {pregunta_id: opcion_correcta_id} para las primeras `cuantas` preguntas."""
    cps = list(cuestionario.cuestionario_preguntas.select_related("pregunta").order_by("orden"))
    if cuantas is not None:
        cps = cps[:cuantas]
    return {
        str(cp.pregunta_id): cp.pregunta.opciones.get(es_correcta=True).id
        for cp in cps
    }
