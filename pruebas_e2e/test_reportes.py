"""Reporte de intentos: filtros, acordeón, exportación y confirmaciones."""
from decimal import Decimal

from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles
from apps.evaluaciones.models import Intento

from .base import PruebaNavegador


class ReporteIntentosTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.docente = crear_usuario("prof", "docente")
        self.cuestionario = crear_cuestionario(num_preguntas=2)
        for codigo, nombre, nota in (("E1", "Ana Gómez", "4.00"), ("E1", "Ana Gómez", "2.00"), ("E2", "Beto Ruiz", "1.50")):
            Intento.objects.create(
                cuestionario=self.cuestionario, participante_codigo=codigo, participante_nombre=nombre,
                estado="finalizado", calificacion=Decimal(nota), aprobado=Decimal(nota) >= 3,
            )
        Intento.objects.create(cuestionario=self.cuestionario, participante_codigo="E3", participante_nombre="Caro Paz", estado="en_progreso")

    def test_interacciones(self):
        pg, errores = self.abrir(f"/cuestionarios/{self.cuestionario.id}/intentos/", self.docente, aceptar_dialogos=False)
        visibles = lambda selector: pg.locator(f"{selector}:visible").count()
        self.assertEqual(visibles(".fila-estudiante"), 3)
        self.assertIn("50,0 % de 2 con nota", pg.inner_text(".metricas"))

        pg.click('.chip-filtro[data-filtro="aprobado"]')
        self.assertEqual(visibles(".fila-estudiante"), 1)
        self.assertIn("Mostrando 1 de 3", pg.inner_text("#contador-resultados"))
        pg.click('.chip-filtro[data-filtro="pendiente"]')
        self.assertIn("Caro", pg.inner_text(".fila-estudiante:visible"))

        pg.click('.chip-filtro[data-filtro="todos"]')
        pg.fill("#filtro-busqueda", "zzz")
        self.assertTrue(pg.is_visible("#vista-estudiantes .fila-sin-resultados"))
        self.assertTrue(pg.get_attribute('[data-ref="exportar"]', "href").endswith("?q=zzz"))
        pg.click('#vista-estudiantes [data-accion="limpiar-filtros"]')
        self.assertEqual(visibles(".fila-estudiante"), 3)

        pg.fill("#filtro-busqueda", "ana")
        pg.click(".fila-estudiante:visible [data-acordeon]")
        self.assertEqual(pg.get_attribute(".fila-estudiante:visible [data-acordeon]", "aria-expanded"), "true")
        self.assertEqual(visibles(".detalle-intentos__item"), 2)
        self.capturar(pg, "reporte_intentos")

        # Anular pide confirmación; al cancelar no se borra nada
        pg.click(".detalle-intentos__item:visible >> nth=0 >> text=Anular")
        self.assertTrue(self.dialogos and "Anular el intento" in self.dialogos[-1])
        self.assertEqual(Intento.objects.count(), 4)

        pg.focus("#btn-tab-estudiantes")
        pg.keyboard.press("ArrowRight")
        self.assertTrue(pg.is_visible("#vista-historial"))
        self.assertEqual(visibles(".fila-historial"), 2)  # la búsqueda sigue aplicada
        self.assertEqual(errores, [])
