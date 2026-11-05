"""Importación desde Excel: subir, corregir una fila y guardar."""
import os
import shutil
import tempfile

from django.test import override_settings
from openpyxl import Workbook

from apps.banco_preguntas.models import Pregunta
from apps.core.tests.factories import crear_usuario, sembrar_roles
from apps.importaciones.services import COLUMNAS

from .base import PruebaNavegador


class ImportacionTests(PruebaNavegador):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.ajuste = override_settings(MEDIA_ROOT=self.media)
        self.ajuste.enable()
        sembrar_roles()
        self.docente = crear_usuario("prof", "docente")
        self.excel = os.path.join(self.media, "preguntas.xlsx")
        libro = Workbook()
        hoja = libro.active
        hoja.title = "preguntas"
        hoja.append(COLUMNAS)
        hoja.append(["Lectura Crítica", "MULTIPLE", "", "¿Qué propone el autor?", "Uno", "Dos", "Tres", "Cuatro", "B", "", 1])
        # Fila con error y contenido que antes rompía el botón Corregir
        hoja.append(["Inglés", "ABIERTA", "", "L'autor <img src=x onerror=\"window.__x=1\">", "", "", "", "", "A", "", 1])
        # Pregunta con un texto de apoyo largo (se recorta con «Ver más»)
        hoja.append(["Ciudadanas", "V_F", "Párrafo largo. " * 80, "La constitución es de 1991", "Verdadero", "Falso", "", "", "A", "Año de la constituyente", 2])
        libro.save(self.excel)

    def tearDown(self):
        self.ajuste.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def test_flujo_completo(self):
        pg, errores = self.abrir("/preguntas/importar/", self.docente)
        pg.click('#form-importar button[type="submit"]')  # sin archivo no se envía
        self.assertIn("/preguntas/importar/", pg.url)

        pg.set_input_files('#form-importar input[type="file"]', self.excel)
        self.assertIn("preguntas.xlsx", pg.inner_text('[data-ref="nombre-archivo"]'))
        pg.click('#form-importar button[type="submit"]')
        pg.wait_for_url("**/importar/previsualizar/")
        self.assertIsNone(pg.evaluate("window.__x"))

        # Cada pregunta se ve completa; las filas con error van primero
        tarjetas = pg.locator(".pregunta-importada")
        self.assertEqual(tarjetas.count(), 3)
        self.assertEqual(tarjetas.first.get_attribute("data-estado"), "error")
        self.assertIn("L'autor <img", tarjetas.first.inner_text())  # se muestra como texto
        self.assertEqual(pg.locator(".pregunta-importada--error .campo-error").count(), 1)  # el tipo
        correcta = pg.locator("#fila-2 .opcion-importada--correcta")
        self.assertIn("Dos", correcta.inner_text())
        self.assertIn("Correcta", correcta.inner_text())

        # Texto largo recortado con «Ver más»
        ver_mas = pg.locator("#fila-4 .ver-mas")
        self.assertEqual(ver_mas.count(), 1)
        self.assertEqual(pg.locator("#fila-2 .ver-mas").count(), 0)  # los textos cortos no lo llevan
        ver_mas.click()
        self.assertEqual(ver_mas.get_attribute("aria-expanded"), "true")

        # Filtros por estado, texto y categoría
        visibles = lambda: pg.locator(".pregunta-importada:visible").count()
        pg.click('[data-filtro-estado="error"]')
        self.assertEqual(visibles(), 1)
        pg.click('[data-filtro-estado="todas"]')
        pg.fill("#filtro-texto", "constitucion")  # sin tilde también encuentra
        self.assertEqual(visibles(), 1)
        pg.fill("#filtro-texto", "zzz")
        self.assertTrue(pg.is_visible("#revision-sin-resultados"))
        pg.click('[data-accion="limpiar-filtros"]')
        pg.select_option("#filtro-categoria", "Ciudadanas")
        self.assertEqual(visibles(), 1)
        pg.select_option("#filtro-categoria", "")
        self.capturar(pg, "importacion_revision")

        # No importar una fila y volver a incluirla
        pg.click("#fila-4 button[value='excluir']")
        pg.wait_for_url("**/previsualizar/#fila-4")
        self.assertEqual(pg.get_attribute("#fila-4", "data-estado"), "excluida")
        self.assertIn("Se guardarán 1 de 3", pg.inner_text(".barra-guardar"))
        pg.click("#fila-4 button[value='incluir']")
        pg.wait_for_url("**/previsualizar/#fila-4")
        self.assertEqual(pg.get_attribute("#fila-4", "data-estado"), "valida")

        pg.click(".pregunta-importada--error [data-corregir]")
        self.assertIn("L'autor <img", pg.input_value("#c-pregunta"))
        self.assertFalse(pg.is_hidden('#modal-correccion [data-ref="errores"]'))
        self.assertIsNone(pg.evaluate("window.__x"))
        pg.select_option("#c-tipo", "V_F")
        self.assertTrue(pg.is_disabled("#c-opcion-c"))
        self.assertEqual(pg.input_value("#c-opcion-a"), "Verdadero")
        pg.fill("#c-pregunta", "El autor es optimista")
        pg.click('#form-correccion button[type="submit"]')
        pg.wait_for_url("**/previsualizar/#fila-3")  # vuelve a la pregunta editada
        self.assertEqual(pg.locator(".pregunta-importada--error").count(), 0)
        self.assertEqual(pg.get_attribute("#fila-3", "data-estado"), "valida")
        self.capturar(pg, "importacion")

        pg.click('form[action$="/confirmar/"] button')
        pg.wait_for_load_state("networkidle")
        self.assertEqual(Pregunta.objects.count(), 3)
        self.assertTrue(Pregunta.objects.filter(tipo="V_F", enunciado="El autor es optimista").exists())
        self.assertIn("guardada", pg.inner_text("h1"))
        self.assertEqual(errores, [])
