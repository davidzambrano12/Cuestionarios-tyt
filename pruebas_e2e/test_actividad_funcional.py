"""Recorrido consecutivo de la actividad con dos estudiantes y dos ejes."""
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.utils import timezone
from openpyxl import load_workbook

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.core.tests.factories import CLAVE, crear_usuario, sembrar_roles
from apps.cuestionarios.models import Cuestionario
from apps.evaluaciones.models import Intento, RespuestaIntento

from .base import PruebaNavegador


class ActividadFuncionalTests(PruebaNavegador):
    def capturar(self, pagina, nombre):
        carpeta = os.environ.get("E2E_CAPTURAS")
        if carpeta:
            pagina.evaluate("window.scrollTo(0, 0)")
            pagina.screenshot(
                path=Path(carpeta) / f"{nombre}.png", full_page=True, animations="disabled",
            )

    def entrar(self, pagina, usuario, destino):
        pagina.fill("#username", usuario.username)
        pagina.fill("#password", CLAVE)
        pagina.click('[data-ref="enviar"]')
        pagina.wait_for_url(f"**/dashboard/{destino}/")

    def salir(self, pagina):
        pagina.click(".menu-cuenta__boton")
        pagina.click("#menu-cuenta-lista [data-cerrar-sesion]")
        pagina.wait_for_url("**/login/")

    def test_recorrido_completo(self):
        sembrar_roles()
        docente = crear_usuario("docente_tyt", "docente")
        ana = crear_usuario("ana_tyt", "estudiante")
        luis = crear_usuario("luis_tyt", "estudiante")
        hoy = timezone.localdate()
        periodo = PeriodoAcademico.objects.create(
            anio=hoy.year, numero=1, fecha_inicio=hoy - timedelta(days=2),
            fecha_fin=hoy + timedelta(days=2),
        )
        curso = Curso.objects.create(periodo=periodo, asignatura="Competencias Saber TyT", docente=docente)
        for estudiante in (ana, luis):
            Matricula.objects.create(curso=curso, estudiante=estudiante)

        pagina, errores = self.abrir("/login/")
        pagina.emulate_media(reduced_motion="reduce")
        self.entrar(pagina, docente, "docente")
        pagina.goto(self.live_server_url + "/cuestionarios/crear/")
        pagina.fill("#campo-nombre", "Actividad funcional Saber TyT")
        pagina.fill("#campo-descripcion", "Lee cada pregunta y selecciona una opción.")
        ahora = timezone.localtime()
        pagina.fill("#campo-apertura", (ahora - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
        pagina.fill("#campo-cierre", (ahora + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"))
        pagina.fill("#campo-tiempo", "20")
        pagina.check(f'input[name="cursos"][value="{curso.pk}"]')
        self.capturar(pagina, "01_configuracion")
        pagina.click('.pasos__boton[data-ir-paso="2"]')
        pagina.fill("#campo-intentos", "1")
        for campo in ("mezclar_preguntas", "mezclar_respuestas"):
            pagina.locator(f'input[name="{campo}"]').uncheck()
        self.capturar(pagina, "02_politicas")
        pagina.click('button[value="borrador"]')
        pagina.wait_for_url("**/editar/")
        cuestionario = Cuestionario.objects.get()
        self.assertEqual(cuestionario.estado, "borrador")
        editar = pagina.url
        pagina.goto(self.live_server_url + "/preguntas/importar/")

        with TemporaryDirectory() as carpeta:
            evidencias = os.environ.get("E2E_CAPTURAS")
            ruta = Path(evidencias or carpeta)
            ruta.mkdir(parents=True, exist_ok=True)
            with pagina.expect_download() as descarga:
                pagina.click("#plantilla")
            original = ruta / "03_plantilla_descargada.xlsx"
            descarga.value.save_as(original)
            libro = load_workbook(original)
            self.assertIn("instrucciones", libro.sheetnames)
            hoja = libro["preguntas"]
            hoja.delete_rows(2, hoja.max_row)
            cuantitativa = ["Razonamiento Cuantitativo", "MULTIPLE", "", "¿Cuánto es el 25 % de 80?", "20", "25", "30", "40", "A", "80 × 0,25 = 20.", 1]
            lectura = ["Lectura Crítica", "MULTIPLE", "El bus salió tarde por la lluvia.", "¿Por qué salió tarde el bus?", "Por la lluvia", "Por tráfico", "Por mantenimiento", "Por falta de pasajeros", "A", "El texto menciona la lluvia.", 1]
            hoja.append(cuantitativa)
            hoja.append(lectura)
            hoja.append([*lectura[:3], "", *lectura[4:8], "Z", *lectura[9:]])
            hoja.append(cuantitativa)
            diligenciada = ruta / "04_plantilla_diligenciada.xlsx"
            libro.save(diligenciada)
            pagina.select_option('[name="cuestionario"]', str(cuestionario.pk))
            pagina.set_input_files('input[name="archivo"]', diligenciada)
            pagina.click('#form-importar button[type="submit"]')
            pagina.wait_for_url("**/importar/previsualizar/")
            for estado, total in (("valida", 2), ("error", 1), ("duplicada", 1)):
                self.assertEqual(pagina.locator(f'.pregunta-importada[data-estado="{estado}"]').count(), total)
            self.capturar(pagina, "05_revision_importacion")
            pagina.click('form[action$="/confirmar/"] button')
            self.responder_confirmacion(pagina)
            pagina.wait_for_url("**/importar/confirmar/")

        self.assertEqual(cuestionario.cuestionario_preguntas.count(), 2)
        self.capturar(pagina, "06_importacion_confirmada")
        pagina.goto(editar)
        with pagina.expect_navigation():
            pagina.click('button[value="publicar"]')
        cuestionario.refresh_from_db()
        self.assertEqual(cuestionario.estado, "disponible")
        self.capturar(pagina, "07_publicada")
        self.salir(pagina)

        ruta_inicio = f"/evaluacion/iniciar/{cuestionario.pk}/"
        ruta_reporte = f"/cuestionarios/{cuestionario.pk}/intentos/"
        for estudiante, opciones, nota in ((ana, (0, 0), "5.00"), (luis, (0, 1), "2.50")):
            self.entrar(pagina, estudiante, "estudiante")
            self.capturar(pagina, f"08_disponible_{estudiante.username}")
            pagina.locator(f'a[href="{ruta_inicio}"]').first.click()
            pagina.wait_for_selector(".option-card")
            self.assertRegex(pagina.inner_text('[data-ref="reloj"]'), r"^\d\d:\d\d:\d\d$")
            csrf = pagina.locator('#form-evaluacion input[name="csrfmiddlewaretoken"]').input_value()
            for indice, opcion in enumerate(opciones):
                if indice:
                    pagina.click('[data-accion="siguiente"]')
                pagina.locator(".option-card").nth(opcion).click()
                pagina.wait_for_function("document.querySelector('[data-ref=guardado]').dataset.estado === 'ok'")
            pagina.click('[data-accion="entregar"]')
            pagina.wait_for_function("document.querySelector('dialog.confirmacion').getAnimations().length === 0")
            self.capturar(pagina, f"09_entrega_{estudiante.username}")
            self.responder_confirmacion(pagina)
            pagina.wait_for_url("**/resultado/")
            intento = Intento.objects.filter(cuestionario=cuestionario).latest("id")
            self.assertEqual(intento.calificacion, Decimal(nota))
            self.assertIsNotNone(intento.fecha_fin)
            self.assertEqual(intento.respuestas.count(), 2)
            self.capturar(pagina, f"10_resultado_{estudiante.username}")
            fecha_entrega = intento.fecha_fin
            reenvio = pagina.request.post(
                f"{self.live_server_url}/evaluacion/{intento.pk}/finalizar/",
                form={"csrfmiddlewaretoken": csrf, "respuestas_json": "{}"},
            )
            self.assertTrue(reenvio.url.endswith("/resultado/"))
            intento.refresh_from_db()
            self.assertEqual((intento.fecha_fin, intento.calificacion), (fecha_entrega, Decimal(nota)))
            self.assertEqual(intento.respuestas.count(), 2)
            pagina.goto(self.live_server_url + ruta_inicio)
            self.assertEqual(Intento.objects.filter(cuestionario=cuestionario, participante_codigo=intento.participante_codigo).count(), 1)
            self.assertEqual(pagina.goto(self.live_server_url + ruta_reporte).status, 403)
            pagina.goto(self.live_server_url + "/dashboard/estudiante/")
            self.salir(pagina)

        self.entrar(pagina, docente, "docente")
        pagina.goto(self.live_server_url + ruta_reporte)
        self.assertIn("3,75", pagina.inner_text(".metricas"))
        self.assertIn("50,0 % de 2 con nota", pagina.inner_text(".metricas"))
        self.assertEqual(RespuestaIntento.objects.filter(intento__cuestionario=cuestionario, es_correcta=True).count(), 3)
        analisis = pagina.locator('section[aria-labelledby="analisis-evaluacion"]')
        ejes = analisis.locator("table").first.locator("tbody tr")
        self.assertIn("Razonamiento Cuantitativo", ejes.nth(0).inner_text())
        self.assertIn("100", ejes.nth(0).inner_text())
        self.assertIn("Lectura Crítica", ejes.nth(1).inner_text())
        self.assertIn("50", ejes.nth(1).inner_text())
        self.assertIn("¿Por qué salió tarde el bus?", analisis.locator("table").nth(1).locator("tbody tr").first.inner_text())
        self.capturar(pagina, "11_reporte_docente")
        self.assertEqual(errores, [])
