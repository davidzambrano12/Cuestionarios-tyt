"""Módulo B: importación desde Excel con validación previa (dry-run)."""
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from openpyxl import Workbook

from apps.banco_preguntas.models import Pregunta
from apps.cuestionarios.models import CuestionarioPregunta
from apps.importaciones.models import Importacion
from apps.importaciones.services import COLUMNAS
from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles

FILA_VALIDA = ["Lectura Crítica", "MULTIPLE", "", "¿Qué propone el autor?",
               "Uno", "Dos", "Tres", "Cuatro", "B", "Explicación", 1]
FILA_ERROR = ["Lectura Crítica", "ABIERTA", "", "Tipo inválido", "", "", "", "", "A", "", 1]
FILA_VF = ["Ciudadanas", "V_F", "", "La constitución es de 1991", "Verdadero", "Falso", "", "", "A", "", 2]


def excel(*filas):
    wb = Workbook()
    ws = wb.active
    ws.title = "preguntas"
    ws.append(COLUMNAS)
    for fila in filas:
        ws.append(fila)
    buffer = io.BytesIO()
    wb.save(buffer)
    return SimpleUploadedFile(
        "preguntas.xlsx", buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class ImportacionExcelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.docente = crear_usuario("prof", "docente")

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.client.force_login(self.docente)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def _subir(self, archivo, **extra):
        return self.client.post("/preguntas/importar/", {"archivo": archivo, **extra})

    def test_previsualizacion_clasifica_filas_sin_guardar(self):
        r = self._subir(excel(FILA_VALIDA, FILA_ERROR, FILA_VALIDA, FILA_VF))
        self.assertRedirects(r, "/preguntas/importar/previsualizar/", fetch_redirect_response=False)

        resultado = self.client.get("/preguntas/importar/previsualizar/").context["resultado"]
        self.assertEqual(resultado.total_filas, 4)
        self.assertEqual(len(resultado.validas), 2)
        self.assertEqual(len(resultado.con_error), 1)
        self.assertEqual(len(resultado.duplicadas), 1)
        # El error indica la fila real de Excel (cabecera = fila 1)
        self.assertEqual(resultado.con_error[0].fila_excel, 3)
        self.assertEqual(resultado.duplicadas[0].fila_excel, 4)
        # Dry-run: nada se persiste todavía
        self.assertEqual(Pregunta.objects.count(), 0)
        self.assertEqual(Importacion.objects.count(), 0)

    def test_confirmar_guarda_validas_y_registra_bitacora(self):
        self._subir(excel(FILA_VALIDA, FILA_ERROR, FILA_VF))
        self.client.post("/preguntas/importar/confirmar/")

        self.assertEqual(Pregunta.objects.count(), 2)
        importacion = Importacion.objects.get()
        self.assertEqual(
            (importacion.total_filas, importacion.filas_validas, importacion.filas_con_error),
            (3, 2, 1),
        )
        self.assertEqual(importacion.resultado, "parcial")
        multiple = Pregunta.objects.get(tipo="MULTIPLE")
        self.assertEqual(multiple.opciones.get(es_correcta=True).texto, "Dos")

    def test_importar_hacia_un_cuestionario(self):
        cuestionario = crear_cuestionario(num_preguntas=0, visibilidad="privado", creado_por=self.docente)
        self._subir(excel(FILA_VALIDA, FILA_VF), cuestionario=cuestionario.id)
        self.client.post("/preguntas/importar/confirmar/")
        self.assertEqual(CuestionarioPregunta.objects.filter(cuestionario=cuestionario).count(), 2)

    def test_reimportar_detecta_duplicadas_del_banco(self):
        self._subir(excel(FILA_VALIDA))
        self.client.post("/preguntas/importar/confirmar/")
        self._subir(excel(FILA_VALIDA))
        resultado = self.client.get("/preguntas/importar/previsualizar/").context["resultado"]
        self.assertEqual(len(resultado.duplicadas), 1)
        self.assertEqual(len(resultado.validas), 0)

    def test_rechaza_archivos_que_no_son_excel(self):
        archivo = SimpleUploadedFile("preguntas.csv", b"a,b,c", content_type="text/csv")
        r = self._subir(archivo)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)

    def test_cancelar_libera_la_importacion(self):
        self._subir(excel(FILA_VALIDA))
        self.client.get("/preguntas/importar/cancelar/")
        self.assertNotIn("importacion_pendiente", self.client.session)
        r = self.client.post("/preguntas/importar/confirmar/")
        self.assertEqual(Pregunta.objects.count(), 0)
        self.assertEqual(r.status_code, 302)


class RevisionImportacionTests(TestCase):
    """Revisión antes de guardar: ver cada pregunta completa, editarla o excluirla."""

    URL = "/preguntas/importar/previsualizar/"

    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.docente = crear_usuario("prof", "docente")

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.client.force_login(self.docente)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def _subir(self, *filas):
        self.client.post("/preguntas/importar/", {"archivo": excel(*filas)})

    def _resultado(self):
        return self.client.get(self.URL).context["resultado"]

    def test_muestra_la_pregunta_completa_con_la_respuesta_correcta(self):
        con_contexto = ["Lectura Crítica", "MULTIPLE", "Texto de apoyo largo", "¿Cuál es la tesis?",
                        "Uno", "Dos", "Tres", "Cuatro", "C", "Porque sí", 1]
        self._subir(con_contexto)
        r = self.client.get(self.URL)
        self.assertContains(r, "Texto de apoyo largo")
        self.assertContains(r, "Porque sí")
        fila = r.context["resultado"].validas[0]
        self.assertEqual([o["letra"] for o in fila.opciones_vista if o["es_correcta"]], ["C"])
        self.assertContains(r, "opcion-importada--correcta", count=1)

    def test_resalta_los_campos_con_error(self):
        sin_opciones = ["Lectura Crítica", "MULTIPLE", "", "Enunciado", "Uno", "", "Tres", "", "Z", "", 0]
        self._subir(sin_opciones)
        fila = self._resultado().con_error[0]
        self.assertEqual(fila.campos_con_error, {"opcion_b", "opcion_d", "respuesta_correcta", "puntaje"})
        self.assertContains(self.client.get(self.URL), "campo-error", count=4)

    def test_contenido_del_excel_se_muestra_como_texto(self):
        self._subir(["Inglés", "MULTIPLE", "", "<script>alert(1)</script>", "<b>A</b>", "B", "C", "D", "A", "", 1])
        r = self.client.get(self.URL)
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(r, "<b>A</b>")

    def test_excluir_e_incluir_una_fila(self):
        self._subir(FILA_VALIDA, FILA_VF)
        r = self.client.post("/preguntas/importar/excluir/", {"fila_excel": 2, "accion": "excluir"})
        self.assertRedirects(r, f"{self.URL}#fila-2", fetch_redirect_response=False)
        resultado = self._resultado()
        self.assertEqual([f.fila_excel for f in resultado.excluidas], [2])
        self.assertEqual(len(resultado.validas), 1)
        self.assertContains(self.client.get(self.URL), "Se guardarán <strong>1</strong> de 2")

        self.client.post("/preguntas/importar/excluir/", {"fila_excel": 2, "accion": "incluir"})
        self.assertEqual(len(self._resultado().validas), 2)

    def test_confirmar_no_guarda_las_excluidas(self):
        self._subir(FILA_VALIDA, FILA_VF)
        self.client.post("/preguntas/importar/excluir/", {"fila_excel": 3, "accion": "excluir"})
        self.client.post("/preguntas/importar/confirmar/")
        self.assertEqual(list(Pregunta.objects.values_list("tipo", flat=True)), ["MULTIPLE"])
        importacion = Importacion.objects.get()
        self.assertEqual((importacion.total_filas, importacion.filas_validas), (2, 1))
        self.assertEqual(importacion.resultado, "exitosa")  # excluir es una decisión, no un fallo

    def test_excluir_la_original_libera_a_su_duplicada(self):
        self._subir(FILA_VALIDA, FILA_VALIDA)
        duplicada = self._resultado().duplicadas[0]
        self.assertEqual((duplicada.fila_excel, duplicada.duplicada_de_fila), (3, 2))
        self.client.post("/preguntas/importar/excluir/", {"fila_excel": 2})
        resultado = self._resultado()
        self.assertEqual([f.fila_excel for f in resultado.validas], [3])

    def test_duplicada_del_banco_enlaza_la_pregunta_existente(self):
        self._subir(FILA_VALIDA)
        self.client.post("/preguntas/importar/confirmar/")
        existente = Pregunta.objects.get()
        self._subir(FILA_VALIDA)
        r = self.client.get(self.URL)
        self.assertEqual(r.context["resultado"].duplicadas[0].duplicada_de_id, existente.id)
        self.assertContains(r, f'href="/preguntas/{existente.id}/editar/"')

    def test_editar_vuelve_a_la_misma_fila(self):
        self._subir(FILA_VALIDA, FILA_ERROR)
        datos = dict(zip(COLUMNAS, FILA_ERROR))
        datos.update(tipo="MULTIPLE", opcion_a="A1", opcion_b="B1", opcion_c="C1", opcion_d="D1", fila_excel=3)
        r = self.client.post("/preguntas/importar/corregir/", datos)
        self.assertRedirects(r, f"{self.URL}#fila-3", fetch_redirect_response=False)
        self.assertEqual(len(self._resultado().validas), 2)

    def test_errores_aparecen_primero(self):
        self._subir(FILA_VALIDA, FILA_VF, FILA_ERROR)
        orden = [f.estado for f in self._resultado().filas_para_revision]
        self.assertEqual(orden, ["error", "valida", "valida"])

    def test_excluir_sin_importacion_en_curso(self):
        r = self.client.post("/preguntas/importar/excluir/", {"fila_excel": 2})
        self.assertRedirects(r, "/preguntas/importar/", fetch_redirect_response=False)
