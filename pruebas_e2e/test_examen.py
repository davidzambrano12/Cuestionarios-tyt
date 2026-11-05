"""Sala de examen del estudiante y previsualización docente."""
from decimal import Decimal

from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles
from apps.evaluaciones.models import Intento, RespuestaIntento

from .base import PruebaNavegador


class ExamenTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.estudiante = crear_usuario("alumno", "estudiante", codigo="EST-1")
        self.docente = crear_usuario("prof", "docente")
        self.cuestionario = crear_cuestionario(num_preguntas=3)
        pregunta = self.cuestionario.cuestionario_preguntas.order_by("orden").first().pregunta
        # Contenido malicioso: debe mostrarse como texto, nunca ejecutarse
        pregunta.enunciado = '<img src=x onerror="window.__xss=1"> ¿Cuál es correcta?'
        pregunta.texto_base = "Texto base de lectura crítica " * 20
        pregunta.save()
        opcion = pregunta.opciones.order_by("orden").last()
        opcion.texto = "<b>negrita</b>"
        opcion.save()

    def test_presentar_y_entregar(self):
        pg, errores = self.abrir(f"/evaluacion/iniciar/{self.cuestionario.id}/", self.estudiante)
        pg.wait_for_selector(".option-card")
        self.assertIn("<img", pg.inner_text('[data-ref="enunciado"]'))
        self.assertIsNone(pg.evaluate("window.__xss"))
        self.assertIn("<b>negrita</b>", pg.inner_text('[data-ref="opciones"]'))
        self.assertRegex(pg.inner_text('[data-ref="reloj"]'), r"^\d\d:\d\d:\d\d$")

        # Autoguardado
        pg.click(".option-card >> nth=0")
        pg.wait_for_function("document.querySelector('[data-ref=guardado]').dataset.estado === 'ok'")
        intento = Intento.objects.get()
        self.assertEqual(RespuestaIntento.objects.filter(intento=intento, es_correcta=True).count(), 1)
        self.assertEqual(pg.get_attribute(".option-card >> nth=0", "aria-checked"), "true")
        self.capturar(pg, "sala")

        # Navegación por el mapa y recuperación tras recargar
        pg.click('[data-accion="siguiente"]')
        pg.click(".option-card >> nth=1")
        pg.click('[data-ref="grilla"] button >> nth=2')
        self.assertEqual(pg.inner_text('[data-ref="indice"]'), "3")
        self.assertIn("2 respondidas", pg.inner_text('[data-ref="resumen"]'))
        pg.reload()
        pg.wait_for_selector(".option-card")
        self.assertIn("2 respondidas", pg.inner_text('[data-ref="resumen"]'))

        # Entrega y resultado
        pg.click('[data-accion="entregar"]')
        pg.wait_for_url("**/resultado/")
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "finalizado")
        self.assertEqual(intento.calificacion, Decimal("1.67"))  # 1/3 × 5
        self.assertIn("No aprobado", pg.inner_text(".resumen-resultado"))
        pg.click('.chip-filtro[data-filtro="correcta"]')
        self.assertEqual(pg.locator(".revision:visible").count(), 1)
        self.capturar(pg, "resultado")

        pg.goto(f"{self.live_server_url}/dashboard/estudiante/")
        pg.click('[data-pestana="historial"]')
        self.assertIn("No aprobado", pg.inner_text("#pestana-historial"))
        self.capturar(pg, "panel_estudiante")
        self.assertEqual(errores, [])

    def test_previsualizacion_docente(self):
        pg, errores = self.abrir(f"/cuestionarios/{self.cuestionario.id}/previsualizar/", self.docente)
        pg.wait_for_selector(".option-card")
        self.assertEqual(pg.locator(".es-clave").count(), 0)
        self.assertTrue(pg.is_hidden('[data-ref="retroalimentacion"]'))
        pg.click('[data-accion="claves"]')
        self.assertEqual(pg.locator(".es-clave").count(), 1)
        self.assertTrue(pg.is_visible('[data-ref="retroalimentacion"]'))
        primera = self.cuestionario.cuestionario_preguntas.order_by("orden").first().pregunta_id
        self.assertTrue(pg.get_attribute('[data-ref="editar-pregunta"]', "href").endswith(f"?editar={primera}"))
        pg.click(".option-card >> nth=2")
        self.assertIn("33% explorado", pg.inner_text('[data-ref="porcentaje"]'))
        self.assertIn("Fijo", pg.inner_text(".sala-ficha"))
        self.capturar(pg, "previsualizacion")
        self.assertFalse(Intento.objects.exists())
        self.assertEqual(errores, [])
