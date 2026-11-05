"""Barra lateral: contraer/expandir, preferencia recordada y panel en celular."""
from apps.core.tests.factories import crear_usuario, sembrar_roles

from .base import PruebaNavegador

ANCHO_BARRA = "document.getElementById('barra-lateral').getBoundingClientRect().width"


class BarraLateralTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.docente = crear_usuario("prof", "docente")

    def test_contraer_y_recordar(self):
        pg, errores = self.abrir("/dashboard/docente/", self.docente, ancho=1366)
        alternar = "[data-alternar-barra]"
        self.assertEqual(pg.evaluate(ANCHO_BARRA), 250)  # pantalla amplia: expandida
        self.assertEqual(pg.get_attribute(alternar, "aria-expanded"), "true")
        self.assertEqual(pg.get_attribute(".nav-item.active", "aria-current"), "page")

        pg.click(alternar)
        pg.wait_for_function(f"{ANCHO_BARRA} === 72")
        self.assertEqual(pg.get_attribute(alternar, "aria-expanded"), "false")
        self.assertIn("Expandir", pg.inner_text(f"{alternar} .nav-item__texto"))

        # Contraída: la etiqueta aparece como texto flotante al pasar el mouse o enfocar
        etiqueta = '.nav-item[href="/preguntas/"] .nav-item__texto'
        self.assertEqual(pg.eval_on_selector(etiqueta, "e => getComputedStyle(e).opacity"), "0")
        pg.hover('.nav-item[href="/preguntas/"]')
        pg.wait_for_function(f"getComputedStyle(document.querySelector('{etiqueta}')).opacity === '1'")
        self.capturar(pg, "barra_contraida")

        # La preferencia se recuerda al navegar, sin esperar al JavaScript
        pg.click('.nav-item[href="/preguntas/"]')
        pg.wait_for_url("**/preguntas/")
        self.assertEqual(pg.get_attribute(".app-container", "data-barra"), "contraida")
        self.assertEqual(pg.evaluate(ANCHO_BARRA), 72)

        pg.click(alternar)
        pg.wait_for_function(f"{ANCHO_BARRA} === 250")
        pg.reload()
        self.assertEqual(pg.get_attribute(".app-container", "data-barra"), "expandida")
        self.assertEqual(errores, [])

    def test_laptop_pequena_arranca_contraida(self):
        pg, errores = self.abrir("/dashboard/docente/", self.docente, ancho=1100)
        self.assertEqual(pg.evaluate(ANCHO_BARRA), 72)
        self.assertEqual(pg.get_attribute("[data-alternar-barra]", "aria-expanded"), "false")
        pg.click("[data-alternar-barra]")
        pg.wait_for_function(f"{ANCHO_BARRA} === 250")
        self.assertEqual(errores, [])

    def test_celular(self):
        pg, errores = self.abrir("/dashboard/docente/", self.docente, ancho=375, alto=740)
        menu = "[data-abrir-barra]"
        en_pantalla = "document.getElementById('barra-lateral').getBoundingClientRect().left >= 0"
        fuera = "document.getElementById('barra-lateral').getBoundingClientRect().right <= 0"
        barra_inerte = "document.getElementById('barra-lateral').inert"

        # Cerrada: fuera de pantalla y sin foco posible; el contenido usa todo el ancho
        self.assertTrue(pg.evaluate(fuera))
        self.assertTrue(pg.evaluate(barra_inerte))
        self.assertFalse(pg.is_visible("[data-alternar-barra]"))
        self.assertGreaterEqual(pg.evaluate("document.querySelector('.main-content').getBoundingClientRect().width"), 370)

        pg.click(menu)
        pg.wait_for_function(en_pantalla)
        self.assertEqual(pg.get_attribute(menu, "aria-expanded"), "true")
        self.assertFalse(pg.evaluate(barra_inerte))
        self.assertTrue(pg.evaluate("document.activeElement.classList.contains('nav-item')"))
        self.assertTrue(pg.evaluate("document.querySelector('.main-content').inert"))
        self.capturar(pg, "barra_celular")

        pg.keyboard.press("Escape")
        pg.wait_for_function(fuera)
        self.assertTrue(pg.evaluate(barra_inerte))
        self.assertTrue(pg.evaluate("document.activeElement.matches('[data-abrir-barra]')"))

        pg.click(menu)
        pg.wait_for_function(en_pantalla)
        pg.click(".barra-fondo", position={"x": 360, "y": 400})
        pg.wait_for_function(fuera)
        self.assertFalse(pg.evaluate("document.querySelector('.main-content').inert"))

        # Al pasar a escritorio la barra vuelve a su lugar y deja de ser inerte
        pg.set_viewport_size({"width": 1366, "height": 900})
        pg.wait_for_function(f"!{barra_inerte} && {ANCHO_BARRA} === 250")
        self.assertEqual(errores, [])
