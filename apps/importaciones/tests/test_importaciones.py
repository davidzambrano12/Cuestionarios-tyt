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
        cuestionario = crear_cuestionario(num_preguntas=0)
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
