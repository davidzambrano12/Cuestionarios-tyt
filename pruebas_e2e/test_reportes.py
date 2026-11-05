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
        anular = ".detalle-intentos__item:visible >> nth=0 >> text=Anular"
        pg.click(anular)
        # Acción destructiva: botón rojo y el foco arranca en Cancelar
        self.assertIn("btn-danger", pg.get_attribute('dialog.confirmacion [data-ref="aceptar"]', "class"))
        self.assertEqual(pg.evaluate("document.activeElement.dataset.ref"), "cancelar")
        pg.wait_for_function("document.querySelector('dialog.confirmacion').getAnimations().length === 0")
        self.capturar(pg, "confirmar_anular")
        titulo, mensaje = self.responder_confirmacion(pg, aceptar=False)
        self.assertIn("Anular el intento", titulo)
        self.assertIn("no se puede deshacer", mensaje)
        self.assertEqual(Intento.objects.count(), 4)

        # Clic en el fondo también cancela
        pg.click(anular)
        pg.mouse.click(5, 5)
        pg.wait_for_selector("dialog.confirmacion[open]", state="hidden")
        self.assertEqual(Intento.objects.count(), 4)

        # Al aceptar, el formulario se envía y el intento se elimina
        pg.click(anular)
        with pg.expect_navigation():
            self.responder_confirmacion(pg)
        self.assertEqual(Intento.objects.count(), 3)
        self.assertEqual(self.dialogos, [])  # ningún cuadro nativo del navegador
        pg.fill("#filtro-busqueda", "ana")

        pg.focus("#btn-tab-estudiantes")
        pg.keyboard.press("ArrowRight")
        self.assertTrue(pg.is_visible("#vista-historial"))
        self.assertEqual(visibles(".fila-historial"), 1)  # la búsqueda sigue aplicada (a Ana le queda 1 intento)
        self.assertEqual(errores, [])
