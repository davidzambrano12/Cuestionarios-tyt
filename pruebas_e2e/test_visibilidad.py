"""Estudiante en dos cursos: elige para cuál presenta un simulacro institucional."""
from datetime import timedelta

from django.utils import timezone

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles
from apps.evaluaciones.models import Intento

from .base import PruebaNavegador


class ElegirCursoTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.ana = crear_usuario("ana", "estudiante", codigo="E1", first_name="Ana", last_name="Gómez")
        hoy = timezone.localdate()
        periodo = PeriodoAcademico.objects.create(anio=hoy.year, numero=2, fecha_inicio=hoy - timedelta(days=30),
                                                  fecha_fin=hoy + timedelta(days=30))
        self.frameworks = Curso.objects.create(periodo=periodo, asignatura="Electiva Profesional III – Frameworks")
        self.bd = Curso.objects.create(periodo=periodo, asignatura="Bases de Datos II")
        for curso in (self.frameworks, self.bd):
            Matricula.objects.create(curso=curso, estudiante=self.ana)
        self.institucional = crear_cuestionario(num_preguntas=2, nombre="Simulacro institucional")
        self.ajeno = crear_cuestionario(num_preguntas=2, nombre="Parcial de otro curso", visibilidad="privado")

    def test_elegir_curso_y_no_ver_los_ajenos(self):
        pg, errores = self.abrir("/dashboard/estudiante/", self.ana)
        texto = pg.inner_text("main")
        self.assertIn("Simulacro institucional", texto)
        self.assertNotIn("Parcial de otro curso", texto)

        pg.goto(f"{self.live_server_url}/evaluacion/iniciar/{self.institucional.id}/")
        self.assertEqual(pg.locator(".elegir-curso__opcion").count(), 2)
        self.capturar(pg, "elegir_curso")
        pg.check(f'input[name="curso"][value="{self.bd.id}"]')
        with pg.expect_navigation():
            pg.click(".elegir-curso__form button[type=submit]")
        pg.wait_for_selector(".option-card")
        self.assertEqual(Intento.objects.get().curso, self.bd)
        self.assertEqual(errores, [])
