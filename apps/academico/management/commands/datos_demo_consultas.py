"""
Datos de demostración para el módulo de consultas y reportes.

Crea tres períodos (2025-2, 2026-1, 2026-2), cinco cursos, doce estudiantes
matriculados y simulacros cerrados con intentos terminados y respuestas en
varios ejes temáticos. Es repetible: `--limpiar` borra solo lo que este
comando creó (códigos DEMO-* y simulacros «[Demo] …»).

    python manage.py datos_demo_consultas
    python manage.py datos_demo_consultas --limpiar
"""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.banco_preguntas.models import Categoria, Pregunta
from apps.core.models import PerfilUsuario, Rol
from apps.cuestionarios.models import Cuestionario, CuestionarioPregunta
from apps.evaluaciones.models import Intento
from apps.evaluaciones.services import calificar_intento

PREFIJO_CODIGO = "DEMO-"
PREFIJO_SIMULACRO = "[Demo] "
NOMBRES = [
    ("Laura", "Benavides"), ("Andrés", "Muñoz"), ("Valentina", "Rosero"), ("Santiago", "Erazo"),
    ("Camila", "Jojoa"), ("Mateo", "Chávez"), ("Isabella", "Burbano"), ("Juan", "Delgado"),
    ("Sofía", "Guerrero"), ("Daniel", "Ortiz"), ("Mariana", "Insuasty"), ("Samuel", "Narváez"),
]
PERIODOS = [
    (2025, 2, date(2025, 7, 15), date(2025, 12, 10)),
    (2026, 1, date(2026, 2, 1), date(2026, 6, 20)),
    (2026, 2, date(2026, 7, 15), date(2026, 12, 10)),
]
# período → cursos; cada estudiante pasa por un curso en cada período
CURSOS = {(2025, 2): ["Cuarto A"], (2026, 1): ["Quinto A", "Quinto B"], (2026, 2): ["Sexto A", "Sexto B"]}


class Command(BaseCommand):
    help = "Crea períodos, cursos, matrículas e intentos de ejemplo para demostrar las consultas."

    def add_arguments(self, parser):
        parser.add_argument("--limpiar", action="store_true", help="Elimina los datos de demostración creados antes.")

    def handle(self, *args, **opciones):
        if opciones["limpiar"]:
            self._limpiar()
            self.stdout.write(self.style.SUCCESS("Datos de demostración eliminados."))
            return
        with transaction.atomic():
            self._limpiar()
            self._crear()

    def _limpiar(self):
        demo = Cuestionario.objects.filter(nombre__startswith=PREFIJO_SIMULACRO)
        Intento.objects.filter(cuestionario__in=demo).delete()
        Intento.objects.filter(participante_codigo__startswith=PREFIJO_CODIGO).delete()
        CuestionarioPregunta.objects.filter(cuestionario__in=demo).delete()
        demo.delete()
        Matricula.objects.filter(estudiante__perfil__codigo_institucional__startswith=PREFIJO_CODIGO).delete()
        User.objects.filter(perfil__codigo_institucional__startswith=PREFIJO_CODIGO).delete()
        for anio, numero, *_ in PERIODOS:
            for nombre in CURSOS[(anio, numero)]:
                Curso.objects.filter(periodo__anio=anio, periodo__numero=numero, nombre=nombre, intentos__isnull=True,
                                     matriculas__isnull=True).delete()

    def _crear(self):
        azar = random.Random(2026)
        rol = Rol.objects.filter(codigo="estudiante").first()
        if not rol:
            raise CommandError("Falta el rol «estudiante»: ejecuta primero `python manage.py seed_data`.")
        docente = User.objects.filter(perfil__rol__codigo="docente", is_active=True).order_by("id").first()

        preguntas = self._preguntas()
        simulacros = [self._simulacro(f"{PREFIJO_SIMULACRO}Simulacro general {n}", preguntas) for n in (1, 2)]

        estudiantes = []
        for i, (nombre, apellido) in enumerate(NOMBRES, start=1):
            user = User.objects.create(username=f"demo{i:02d}", first_name=nombre, last_name=apellido,
                                       email=f"demo{i:02d}@uniputumayo.edu.co")
            user.set_unusable_password()
            user.save()
            PerfilUsuario.objects.update_or_create(user=user, defaults={
                "rol": rol, "codigo_institucional": f"{PREFIJO_CODIGO}{i:03d}",
            })
            # Habilidad base y mejora por período, para que haya variedad y evolución
            estudiantes.append((user, 0.35 + azar.random() * 0.5, azar.uniform(-0.05, 0.12)))

        total = 0
        for orden_periodo, (anio, numero, inicio, fin) in enumerate(PERIODOS):
            periodo, _ = PeriodoAcademico.objects.get_or_create(
                anio=anio, numero=numero, defaults={"fecha_inicio": inicio, "fecha_fin": fin},
            )
            cursos = [
                Curso.objects.get_or_create(periodo=periodo, nombre=nombre, defaults={
                    "docente": docente if j == 0 else None,
                })[0]
                for j, nombre in enumerate(CURSOS[(anio, numero)])
            ]
            for k, (user, habilidad, mejora) in enumerate(estudiantes):
                curso = cursos[k % len(cursos)]
                Matricula.objects.get_or_create(curso=curso, estudiante=user)
                for n, simulacro in enumerate(simulacros):
                    for intento_n in range(azar.choice([1, 1, 2])):
                        cuando = self._fecha(inicio, fin, azar, (n * 2 + intento_n) / 4)
                        prob = min(0.95, habilidad + mejora * orden_periodo + 0.04 * intento_n)
                        self._presentar(user, simulacro, curso, prob, cuando, azar)
                        total += 1

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {len(PERIODOS)} períodos, {sum(len(c) for c in CURSOS.values())} cursos, "
            f"{len(estudiantes)} estudiantes y {total} intentos terminados."
            + ("" if docente else " (No hay docentes: los cursos quedaron sin docente asignado.)")
        ))

    def _preguntas(self):
        """Hasta 3 preguntas activas por eje (los 4 ejes con más preguntas)."""
        ejes = sorted(Categoria.objects.all(), key=lambda c: -c.preguntas.filter(activa=True).count())[:4]
        preguntas = []
        for eje in ejes:
            preguntas += list(eje.preguntas.filter(activa=True).prefetch_related("opciones").order_by("id")[:3])
        if len(preguntas) < 4:
            raise CommandError("El banco necesita al menos 4 preguntas activas (ejecuta `seed_data` o importa preguntas).")
        return preguntas

    def _simulacro(self, nombre, preguntas):
        simulacro = Cuestionario.objects.create(
            nombre=nombre, descripcion="Generado por datos_demo_consultas.",
            fecha_apertura=timezone.make_aware(datetime(2025, 7, 1)),
            fecha_cierre=timezone.make_aware(datetime(2026, 12, 15)),
            tiempo_limite_minutos=60, intentos_permitidos=3,
            calificacion_maxima=Decimal("5.00"), calificacion_aprobacion=Decimal("3.00"),
            estado="cerrado",
        )
        for orden, pregunta in enumerate(preguntas, start=1):
            CuestionarioPregunta.objects.create(cuestionario=simulacro, pregunta=pregunta, orden=orden,
                                                puntaje_asignado=pregunta.puntaje)
        return simulacro

    @staticmethod
    def _fecha(inicio, fin, azar, avance):
        dias = (fin - inicio).days
        dia = inicio + timedelta(days=int(dias * min(avance, 0.95)) + azar.randint(0, 6))
        return timezone.make_aware(datetime.combine(dia, time(azar.randint(7, 17), azar.choice([0, 15, 30, 45]))))

    @staticmethod
    def _presentar(user, simulacro, curso, prob, cuando, azar):
        intento = Intento.objects.create(
            cuestionario=simulacro, curso=curso, estado="en_progreso",
            participante_nombre=user.get_full_name(), participante_codigo=user.perfil.codigo_institucional,
        )
        Intento.objects.filter(id=intento.id).update(fecha_inicio=cuando)
        intento.refresh_from_db()
        respuestas = {}
        for cp in simulacro.cuestionario_preguntas.select_related("pregunta"):
            opciones = list(cp.pregunta.opciones.all())
            if azar.random() < 0.06:
                continue  # sin responder
            correcta = [o for o in opciones if o.es_correcta]
            erradas = [o for o in opciones if not o.es_correcta]
            elegida = correcta[0] if (azar.random() < prob or not erradas) else azar.choice(erradas)
            respuestas[str(cp.pregunta_id)] = elegida.id
        calificar_intento(intento, respuestas, ahora=cuando + timedelta(minutes=azar.randint(15, 55)))
