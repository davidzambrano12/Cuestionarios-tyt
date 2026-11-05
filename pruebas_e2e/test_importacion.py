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

        pg.click(".fila-importacion--error [data-corregir]")
        self.assertIn("L'autor <img", pg.input_value("#c-pregunta"))
        self.assertFalse(pg.is_hidden('#modal-correccion [data-ref="errores"]'))
        self.assertIsNone(pg.evaluate("window.__x"))
        pg.select_option("#c-tipo", "V_F")
        self.assertTrue(pg.is_disabled("#c-opcion-c"))
        self.assertEqual(pg.input_value("#c-opcion-a"), "Verdadero")
        pg.fill("#c-pregunta", "El autor es optimista")
        pg.click('#form-correccion button[type="submit"]')
        pg.wait_for_load_state("networkidle")
        self.assertEqual(pg.locator(".fila-importacion--error").count(), 0)
        self.capturar(pg, "importacion")

        pg.click('form[action$="/confirmar/"] button')
        pg.wait_for_load_state("networkidle")
        self.assertEqual(Pregunta.objects.count(), 2)
        self.assertTrue(Pregunta.objects.filter(tipo="V_F", enunciado="El autor es optimista").exists())
        self.assertIn("guardada", pg.inner_text("h1"))
        self.assertEqual(errores, [])
