"""Editor de cuestionarios en tres pasos."""
from decimal import Decimal

from apps.banco_preguntas.models import Categoria
from apps.core.tests.factories import crear_pregunta, crear_usuario, sembrar_roles
from apps.cuestionarios.models import Cuestionario

from .base import PruebaNavegador


class EditorCuestionarioTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.docente = crear_usuario("prof", "docente")
        categoria = Categoria.objects.create(nombre="Lectura Crítica")
        self.p1 = crear_pregunta(categoria, "Primera <b>pregunta</b>", puntaje=Decimal("1.00"))
        self.p2 = crear_pregunta(categoria, "Segunda pregunta", puntaje=Decimal("2.50"))

    def test_crear_y_publicar(self):
        pg, errores = self.abrir("/cuestionarios/crear/", self.docente)
        visible = lambda paso: pg.is_visible(f'section[data-paso="{paso}"]')

        # "Continuar" valida el paso; las pestañas navegan libremente
        pg.click('section[data-paso="1"] [data-ir-paso="2"]')
        self.assertTrue(visible(1))
        pg.fill("#campo-nombre", "Simulacro E2E")
        self.assertEqual(pg.inner_text('[data-ref="r-nombre"]'), "Simulacro E2E")
        pg.fill("#campo-apertura", "2026-11-01T08:00")
        pg.fill("#campo-cierre", "2026-11-30T18:00")
        pg.click('section[data-paso="1"] [data-ir-paso="2"]')
        self.assertTrue(visible(1))  # falta la descripción
        pg.click('.pasos__boton[data-ir-paso="2"]')
        self.assertTrue(visible(2))

        # Añadir dos preguntas y quitar una
        pg.click('.pasos__boton[data-ir-paso="3"]')
        self.assertTrue(pg.is_visible('[data-ref="vacio"]'))
        pg.click('section[data-paso="3"] .bloque-formulario__titulo [data-abrir-modal]')
        pg.check(f'.selector-item__casilla[value="{self.p1.id}"]')
        pg.check(f'.selector-item__casilla[value="{self.p2.id}"]')
        self.assertIn("2 seleccionadas", pg.inner_text('#modal-selector-preguntas [data-ref="seleccionadas"]'))
        pg.click('[data-accion="agregar"]')
        self.assertEqual(pg.locator(".pregunta-asignada").count(), 2)
        self.assertIn("Primera <b>pregunta</b>", pg.inner_text(".lista-asignadas"))  # texto, no HTML
        self.assertEqual(pg.inner_text('[data-ref="puntaje"]'), "3,50")
        pg.click('section[data-paso="3"] .bloque-formulario__titulo [data-abrir-modal]')
        self.assertTrue(pg.is_disabled(f'.selector-item__casilla[value="{self.p1.id}"]'))  # ya asignada
        pg.keyboard.press("Escape")
        pg.click(f'.pregunta-asignada[data-id="{self.p2.id}"] [data-quitar]')
        self.assertEqual(pg.inner_text('[data-ref="conteo"]'), "1")

        # Campo obligatorio en un paso oculto: el envío vuelve a ese paso
        pg.click('button[value="publicar"]')
        self.assertTrue(visible(1))
        self.assertFalse(Cuestionario.objects.exists())
        pg.fill("#campo-descripcion", "Lee con atención.")
        self.capturar(pg, "editor_cuestionario")
        pg.click('button[value="publicar"]')
        pg.wait_for_url("**/editar/")
        cuestionario = Cuestionario.objects.get()
        self.assertEqual(cuestionario.estado, "disponible")
        self.assertEqual(list(cuestionario.cuestionario_preguntas.values_list("pregunta_id", flat=True)), [self.p1.id])
        self.assertEqual(errores, [])
