"""Módulo A: CRUD de preguntas, deduplicación por huella y borrado lógico."""
from decimal import Decimal

from django.test import TestCase

from preguntas.models import Categoria, Pregunta
from .factories import crear_usuario, sembrar_roles


class BancoPreguntasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.docente = crear_usuario("prof", "docente")
        cls.categoria = Categoria.objects.create(nombre="Lectura Crítica")

    def setUp(self):
        self.client.force_login(self.docente)

    def _datos_multiple(self, enunciado="¿Cuál es la idea principal?", correcta="C"):
        return {
            "categoria_id": self.categoria.id,
            "tipo": "MULTIPLE",
            "enunciado": enunciado,
            "opcion_a": "Uno", "opcion_b": "Dos", "opcion_c": "Tres", "opcion_d": "Cuatro",
            "correcta": correcta,
            "puntaje": "2.50",
            "retroalimentacion": "Porque sí",
        }

    def test_crear_pregunta_multiple(self):
        self.client.post("/preguntas/crear/", self._datos_multiple())
        pregunta = Pregunta.objects.get()
        self.assertEqual(pregunta.puntaje, Decimal("2.50"))
        self.assertEqual(len(pregunta.huella_contenido), 64)
        opciones = list(pregunta.opciones.order_by("orden"))
        self.assertEqual(len(opciones), 4)
        self.assertEqual([o.es_correcta for o in opciones], [False, False, True, False])

    def test_crear_pregunta_verdadero_falso(self):
        self.client.post("/preguntas/crear/", {
            "categoria_id": self.categoria.id, "tipo": "V_F",
            "enunciado": "El sol es una estrella", "correcta_vf": "V", "puntaje": "1",
        })
        opciones = list(Pregunta.objects.get().opciones.order_by("orden"))
        self.assertEqual([(o.texto, o.es_correcta) for o in opciones], [("Verdadero", True), ("Falso", False)])

    def test_pregunta_duplicada_se_rechaza(self):
        self.client.post("/preguntas/crear/", self._datos_multiple())
        # Mismo contenido con otras mayúsculas/espacios: misma huella
        datos = self._datos_multiple(enunciado="  ¿CUÁL es la idea   principal?")
        self.client.post("/preguntas/crear/", datos)
        self.assertEqual(Pregunta.objects.count(), 1)

    def test_editar_pregunta(self):
        self.client.post("/preguntas/crear/", self._datos_multiple())
        pregunta = Pregunta.objects.get()
        datos = self._datos_multiple(enunciado="Enunciado corregido", correcta="A")
        self.client.post(f"/preguntas/{pregunta.id}/editar/", datos)
        pregunta.refresh_from_db()
        self.assertEqual(pregunta.enunciado, "Enunciado corregido")
        self.assertTrue(pregunta.opciones.get(orden=1).es_correcta)

    def test_editar_get_devuelve_json_para_el_modal(self):
        self.client.post("/preguntas/crear/", self._datos_multiple())
        pregunta = Pregunta.objects.get()
        data = self.client.get(f"/preguntas/{pregunta.id}/editar/").json()
        self.assertEqual(data["enunciado"], pregunta.enunciado)
        self.assertEqual(len(data["opciones"]), 4)

    def test_desactivar_es_borrado_logico(self):
        self.client.post("/preguntas/crear/", self._datos_multiple())
        pregunta = Pregunta.objects.get()
        self.client.post(f"/preguntas/{pregunta.id}/toggle-estado/")
        pregunta.refresh_from_db()
        self.assertFalse(pregunta.activa)
        self.assertTrue(Pregunta.objects.filter(id=pregunta.id).exists())

    def test_banco_lista_las_preguntas(self):
        self.client.post("/preguntas/crear/", self._datos_multiple())
        r = self.client.get("/preguntas/")
        self.assertContains(r, "¿Cuál es la idea principal?")
