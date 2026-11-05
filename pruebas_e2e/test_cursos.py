"""Cursos y matrículas: crear el curso, buscar y matricular estudiantes, retirar."""
from datetime import date

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.core.tests.factories import crear_usuario, sembrar_roles

from .base import PruebaNavegador


class CursosTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.docente = crear_usuario("prof", "docente", first_name="Paula", last_name="Docente")
        for i, (codigo, nombre, apellido) in enumerate((("2026001", "Ana", "Gómez"), ("2026002", "Andrés", "Muñoz"),
                                                         ("2025001", "Beto", "Ruiz")), start=1):
            crear_usuario(f"est{i}", "estudiante", codigo=codigo, first_name=nombre, last_name=apellido)
        self.periodo = PeriodoAcademico.objects.create(anio=2026, numero=2, fecha_inicio=date(2026, 7, 1), fecha_fin=date(2026, 12, 15))

    def test_crear_curso_y_matricular(self):
        pg, errores = self.abrir("/cursos/", self.docente)
        self.assertTrue(pg.is_visible(".nav-item[href='/cursos/'].active"))
        pg.click("text=Nuevo curso")
        pg.select_option("#id_periodo", str(self.periodo.id))
        pg.fill("#id_asignatura", "Electiva Profesional III – Frameworks")
        pg.fill("#id_grupo", "01")
        pg.fill("#id_semestre", "6")
        self.assertEqual(pg.locator("#id_docente").count(), 0)  # el docente no elige a otro
        with pg.expect_navigation():
            pg.click("button[type=submit]")
        curso = Curso.objects.get(asignatura__startswith="Electiva")
        self.assertEqual(curso.docente, self.docente)

        # Buscar y matricular a dos estudiantes de una vez
        pg.fill("#buscar", "2026")  # por código
        with pg.expect_navigation():
            pg.click(".buscar-estudiante button")
        self.assertEqual(pg.locator("[data-candidato]").count(), 2)  # Ana y Andrés
        self.assertTrue(pg.is_disabled("[data-ref='matricular']"))
        pg.check("[data-seleccionar-todos]")
        self.assertIn("Matricular 2 estudiantes", pg.inner_text("[data-ref='matricular']"))
        self.capturar(pg, "cursos_matricular")
        with pg.expect_navigation():
            pg.click("[data-ref='matricular']")
        self.assertEqual(Matricula.objects.filter(curso=curso).count(), 2)
        self.assertEqual(pg.locator(".fila-matricula").count(), 2)

        pg.fill("#filtro-matriculados", "munoz")  # sin tilde también encuentra
        self.assertEqual(pg.locator(".fila-matricula:visible").count(), 1)
        pg.fill("#filtro-matriculados", "")

        # Retirar pide confirmación
        pg.click(".fila-matricula >> nth=0 >> text=Retirar")
        with pg.expect_navigation():
            titulo, _ = self.responder_confirmacion(pg)
        self.assertIn("Retirar a", titulo)
        self.assertEqual(Matricula.objects.filter(curso=curso).count(), 1)
        self.capturar(pg, "cursos_detalle")

        pg.goto(self.live_server_url + "/cursos/")
        self.assertIn("Electiva Profesional III", pg.inner_text(".tabla--cursos"))
        self.capturar(pg, "cursos_listado")
        self.assertEqual(errores, [])
        self.assertEqual(self.dialogos, [])
