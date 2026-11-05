"""Consultas y reportes: filtros dependientes, vistas, paginación y descarga a Excel."""
import io

from django.core.management import call_command
from openpyxl import load_workbook

from apps.academico.models import Curso
from apps.banco_preguntas.models import Categoria
from apps.core.tests.factories import _Silencio, crear_pregunta, crear_usuario, sembrar_roles
from apps.evaluaciones.models import Intento

from .base import PruebaNavegador


class ConsultasTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.admin = crear_usuario("jefe", "admin", is_superuser=True, is_staff=True)
        for eje in ("Lectura Crítica", "Inglés", "Competencias Ciudadanas"):  # banco para los simulacros
            categoria = Categoria.objects.create(nombre=eje)
            for n in range(2):
                crear_pregunta(categoria, f"{eje} {n}")
        call_command("datos_demo_consultas", stdout=_Silencio())

    def test_filtros_vistas_y_excel(self):
        pg, errores = self.abrir("/reportes/consultas/", self.admin, ancho=1366, alto=1000)
        self.assertTrue(pg.is_visible(".nav-item[href='/reportes/consultas/'].active"))
        for filtro in ("anio", "periodo", "curso", "eje", "estudiante"):
            self.assertTrue(pg.is_visible(f"#f-{filtro}"))
        total = Intento.objects.count()
        self.assertIn(str(total), pg.inner_text(".metricas--consulta"))
        self.capturar(pg, "consultas_general")

        # Filtros dependientes: al elegir 2025 solo queda su período y su curso
        pg.select_option("#f-anio", "2025")
        periodos = pg.eval_on_selector_all("#f-periodo option:not([hidden])", "o => o.map(x => x.textContent.trim())")
        self.assertEqual(periodos, ["Todos", "2025-2"])
        cursos = pg.eval_on_selector_all("#f-curso option:not([hidden])", "o => o.map(x => x.textContent.trim())")
        self.assertEqual(cursos, ["Todos", "Cuarto A"])

        # Cambiar el año limpia el curso que ya no corresponde
        sexto = Curso.objects.get(nombre="Sexto A")
        pg.select_option("#f-anio", "2026")
        pg.select_option("#f-curso", str(sexto.id))
        pg.select_option("#f-anio", "2025")
        self.assertEqual(pg.input_value("#f-curso"), "")

        pg.select_option("#f-anio", "2026")
        pg.select_option("#f-curso", str(sexto.id))
        with pg.expect_navigation():
            pg.click("#form-consultas button[type=submit]")
        self.assertIn(f"curso={sexto.id}", pg.url)
        self.assertEqual(pg.locator(".fila-consulta").count(), 10)  # paginado de 10 en 10
        self.capturar(pg, "consultas_sexto_a")

        # Página 2 conserva el filtro
        with pg.expect_navigation():
            pg.click(".paginacion a[rel=next]")
        self.assertIn(f"curso={sexto.id}", pg.url)
        self.assertIn("page=2", pg.url)

        # Historial individual desde la tabla
        with pg.expect_navigation():
            pg.click(".fila-consulta >> nth=0 >> text=Historial")
        self.assertIn("vista=historial", pg.url)
        self.assertTrue(pg.is_visible("#vista-historial table"))
        self.capturar(pg, "consultas_historial")

        # Otras consultas
        for vista, selector in (("ejes", "#vista-ejes"), ("dificultad", "#vista-dificultad"),
                                ("cursos", "#vista-cursos"), ("periodos", "#vista-periodos")):
            with pg.expect_navigation():
                pg.click(f".tabs-header a[href*='vista={vista}']")
            self.assertTrue(pg.is_visible(f"{selector} tbody tr"))
        self.capturar(pg, "consultas_periodos")

        # Excel con los filtros activos
        with pg.expect_download() as descarga:
            pg.click("[data-ref='exportar-consolidado']")
        archivo = descarga.value
        self.assertTrue(archivo.suggested_filename.startswith("reporte_consolidado_2026-2_sexto-a"))
        libro = load_workbook(io.BytesIO(open(archivo.path(), "rb").read()))
        self.assertIn("Calificaciones", libro.sheetnames)

        with pg.expect_navigation():
            pg.click("[data-accion='limpiar']")
        self.assertTrue(pg.url.endswith("/reportes/consultas/"))
        self.assertEqual(errores, [])

    def test_movil(self):
        pg, errores = self.abrir("/reportes/consultas/", self.admin, ancho=375, alto=800)
        ancho = pg.evaluate("document.documentElement.scrollWidth")
        self.assertLessEqual(ancho, 376)  # sin desplazamiento horizontal de la página
        self.capturar(pg, "consultas_movil")
        self.assertEqual(errores, [])
