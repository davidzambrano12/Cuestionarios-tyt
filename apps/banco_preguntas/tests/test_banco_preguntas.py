"""Módulo A: CRUD de preguntas, deduplicación por huella y borrado lógico."""
from decimal import Decimal

from django.test import TestCase

from apps.banco_preguntas.models import Categoria, Pregunta
from apps.core.tests.factories import crear_usuario, sembrar_roles


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


class ListadoBancoTests(TestCase):
    """Búsqueda, filtros y paginación del banco en el servidor."""

    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.docente = crear_usuario("prof", "docente")
        cls.lectura = Categoria.objects.create(nombre="Lectura Crítica")
        cls.ingles = Categoria.objects.create(nombre="Inglés")
        for i in range(20):
            Pregunta.objects.create(categoria=cls.lectura, tipo="MULTIPLE", enunciado=f"Lectura {i}")
        cls.vf = Pregunta.objects.create(categoria=cls.ingles, tipo="V_F", enunciado="Is it true?", activa=False)

    def setUp(self):
        self.client.force_login(self.docente)

    def _ids(self, **filtros):
        return [p.id for p in self.client.get("/preguntas/", filtros).context["pagina"]]

    def test_pagina_de_quince(self):
        r = self.client.get("/preguntas/")
        self.assertEqual(len(r.context["pagina"]), 15)
        self.assertContains(r, "Página 1 de 2")
        self.assertEqual(len(self._ids(page=2)), 6)

    def test_filtros_por_competencia_tipo_estado_y_texto(self):
        self.assertEqual(self._ids(categoria=self.ingles.id), [self.vf.id])
        self.assertEqual(self._ids(tipo="V_F"), [self.vf.id])
        self.assertEqual(self._ids(estado="inactivas"), [self.vf.id])
        self.assertEqual(self._ids(q="true"), [self.vf.id])
        self.assertEqual(self._ids(q=f"P-{self.vf.id}"), [self.vf.id])

    def test_valores_invalidos_se_ignoran(self):
        r = self.client.get("/preguntas/", {"categoria": "x", "tipo": "OTRO", "estado": "?", "page": "99"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["hay_filtros"])

    def test_la_paginacion_conserva_los_filtros(self):
        r = self.client.get("/preguntas/", {"categoria": self.lectura.id})
        self.assertContains(r, f"?categoria={self.lectura.id}&amp;page=2")

    def test_tras_desactivar_vuelve_a_la_misma_pagina_y_filtros(self):
        pregunta = Pregunta.objects.filter(categoria=self.lectura).first()
        r = self.client.post(
            f"/preguntas/{pregunta.id}/toggle-estado/",
            {"volver": f"categoria={self.lectura.id}&page=2&next=https://otro.sitio"},
        )
        self.assertRedirects(r, f"/preguntas/?categoria={self.lectura.id}&page=2", fetch_redirect_response=False)
