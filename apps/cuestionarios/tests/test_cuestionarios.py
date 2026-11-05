"""Módulo C: creación y edición de cuestionarios con sus preguntas."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.academico.models import Curso, PeriodoAcademico
from apps.banco_preguntas.models import Categoria
from apps.cuestionarios.models import Cuestionario
from apps.core.tests.factories import crear_pregunta, crear_usuario, sembrar_roles


class ConfigurarCuestionarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.docente = crear_usuario("prof", "docente")
        categoria = Categoria.objects.create(nombre="Inglés")
        cls.p1 = crear_pregunta(categoria, "Uno", puntaje=Decimal("1.00"))
        cls.p2 = crear_pregunta(categoria, "Dos", puntaje=Decimal("2.50"))
        periodo = PeriodoAcademico.objects.create(anio=2026, numero=2, fecha_inicio=date(2026, 7, 1), fecha_fin=date(2026, 12, 15))
        cls.curso = Curso.objects.create(periodo=periodo, asignatura="Inglés IV", docente=cls.docente)

    def setUp(self):
        self.client.force_login(self.docente)

    def _datos(self, preguntas, **extra):
        datos = {
            "nombre": "Simulacro Inglés",
            "descripcion": "Prueba",
            "fecha_apertura": "2026-11-01T08:00",
            "fecha_cierre": "2026-11-30T18:00",
            "tiempo_limite_minutos": "45",
            "intentos_permitidos": "3",
            "calificacion_maxima": "5.00",
            "calificacion_aprobacion": "3.00",
            "permitir_revision": "on",
            "preguntas_ids": [str(p.id) for p in preguntas],
        }
        datos.update(extra)
        return datos

    def test_crear_cuestionario_en_borrador(self):
        r = self.client.post("/cuestionarios/crear/", self._datos([self.p1, self.p2]))
        cuestionario = Cuestionario.objects.get()
        self.assertRedirects(r, f"/cuestionarios/{cuestionario.id}/editar/", fetch_redirect_response=False)
        self.assertEqual(cuestionario.estado, "borrador")
        self.assertEqual(cuestionario.tiempo_limite_minutos, 45)
        self.assertTrue(cuestionario.permitir_revision)
        self.assertFalse(cuestionario.mezclar_preguntas)
        asignadas = list(cuestionario.cuestionario_preguntas.order_by("orden"))
        self.assertEqual([cp.pregunta_id for cp in asignadas], [self.p1.id, self.p2.id])
        self.assertEqual(asignadas[1].puntaje_asignado, Decimal("2.50"))

    def test_publicar_y_reordenar(self):
        self.client.post("/cuestionarios/crear/", self._datos([self.p1, self.p2]))
        cuestionario = Cuestionario.objects.get()
        self.client.post(
            f"/cuestionarios/{cuestionario.id}/editar/",
            self._datos([self.p2], accion="publicar", nombre="Renombrado", cursos=[self.curso.id]),
        )
        cuestionario.refresh_from_db()
        self.assertEqual(cuestionario.estado, "disponible")
        self.assertEqual(cuestionario.nombre, "Renombrado")
        self.assertEqual(
            list(cuestionario.cuestionario_preguntas.values_list("pregunta_id", "orden")),
            [(self.p2.id, 1)],
        )

    def test_editor_muestra_puntaje_total(self):
        self.client.post("/cuestionarios/crear/", self._datos([self.p1, self.p2]))
        cuestionario = Cuestionario.objects.get()
        r = self.client.get(f"/cuestionarios/{cuestionario.id}/editar/")
        self.assertEqual(r.context["puntaje_total"], Decimal("3.50"))
        self.assertEqual(len(r.context["reactivos_asignados"]), 2)

    def test_previsualizacion_incluye_claves_solo_para_docentes(self):
        self.client.post("/cuestionarios/crear/", self._datos([self.p1]))
        cuestionario = Cuestionario.objects.get()
        r = self.client.get(f"/cuestionarios/{cuestionario.id}/previsualizar/")
        self.assertIn("es_correcta", r.context["preguntas"][0]["opciones"][0])

        estudiante = crear_usuario("alumno", "estudiante")
        self.client.force_login(estudiante)
        r = self.client.get(f"/cuestionarios/{cuestionario.id}/previsualizar/")
        self.assertEqual(r.status_code, 302)

    # --- Validación de reglas R01-R04 -----------------------------------------

    def _rechazado(self, **extra):
        r = self.client.post("/cuestionarios/crear/", self._datos([self.p1], **extra))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Cuestionario.objects.exists())
        return r

    def test_rechaza_cierre_anterior_a_la_apertura(self):
        r = self._rechazado(fecha_cierre="2026-10-01T08:00")
        self.assertContains(r, "La fecha de cierre debe ser posterior a la de apertura.", status_code=400)

    def test_rechaza_aprobacion_mayor_que_la_maxima(self):
        r = self._rechazado(calificacion_aprobacion="6")
        self.assertContains(r, "entre 0 y la calificación máxima", status_code=400)

    def test_rechaza_numeros_invalidos(self):
        r = self._rechazado(tiempo_limite_minutos="abc")
        self.assertContains(r, "El tiempo límite debe ser un número.", status_code=400)

    def test_no_publica_sin_preguntas(self):
        r = self.client.post("/cuestionarios/crear/", self._datos([], accion="publicar"))
        self.assertContains(r, "No se puede publicar un cuestionario sin preguntas.", status_code=400)

    def test_formulario_rechazado_conserva_lo_escrito(self):
        r = self._rechazado(fecha_cierre="2026-10-01T08:00", nombre="Mi simulacro")
        self.assertEqual(r.context["cuestionario"].nombre, "Mi simulacro")
        self.assertEqual([cp.pregunta_id for cp in r.context["reactivos_asignados"]], [self.p1.id])
