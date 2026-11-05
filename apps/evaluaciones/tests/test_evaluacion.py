"""Módulos D y E: presentación del examen, reglas de acceso y calificación."""
import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.evaluaciones.models import Intento, RespuestaIntento
from apps.core.tests.factories import (
    crear_cuestionario,
    crear_usuario,
    respuestas_correctas,
    sembrar_roles,
)


class EvaluacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.estudiante = crear_usuario("alumno", "estudiante", codigo="EST-001")
        cls.otro = crear_usuario("otro", "estudiante", codigo="EST-002")
        cls.docente = crear_usuario("prof", "docente")

    def setUp(self):
        self.cuestionario = crear_cuestionario(num_preguntas=2)
        self.client.force_login(self.estudiante)

    def _iniciar(self, cuestionario=None):
        cuestionario = cuestionario or self.cuestionario
        return self.client.get(f"/evaluacion/iniciar/{cuestionario.id}/")

    def _finalizar(self, intento, respuestas):
        return self.client.post(
            f"/evaluacion/{intento.id}/finalizar/",
            {"respuestas_json": json.dumps(respuestas)},
        )

    # --- Inicio y reglas de acceso -------------------------------------------------

    def test_iniciar_crea_intento_y_abre_la_sala(self):
        r = self._iniciar()
        intento = Intento.objects.get()
        self.assertRedirects(r, f"/evaluacion/{intento.id}/", fetch_redirect_response=False)
        self.assertEqual(intento.participante_codigo, "EST-001")
        self.assertEqual(intento.estado, "en_progreso")
        sala = self.client.get(f"/evaluacion/{intento.id}/")
        self.assertEqual(sala.status_code, 200)
        self.assertEqual(sala.context["total_preguntas"], 2)

    def test_iniciar_de_nuevo_reanuda_el_intento_activo(self):
        self._iniciar()
        self._iniciar()
        self.assertEqual(Intento.objects.count(), 1)

    def test_respeta_el_limite_de_intentos(self):
        self.cuestionario.intentos_permitidos = 1
        self.cuestionario.save()
        self._iniciar()
        self._finalizar(Intento.objects.get(), {})
        self._iniciar()
        self.assertEqual(Intento.objects.count(), 1)

    def test_no_permite_iniciar_fuera_de_fechas(self):
        cerrado = crear_cuestionario(
            fecha_apertura=timezone.now() - timedelta(days=2),
            fecha_cierre=timezone.now() - timedelta(days=1),
        )
        futuro = crear_cuestionario(
            fecha_apertura=timezone.now() + timedelta(days=1),
            fecha_cierre=timezone.now() + timedelta(days=2),
        )
        borrador = crear_cuestionario(estado="borrador")
        for c in (cerrado, futuro, borrador):
            with self.subTest(cuestionario=c.estado):
                self._iniciar(c)
        self.assertFalse(Intento.objects.exists())

    def test_anonimo_no_puede_iniciar(self):
        self.client.logout()
        r = self._iniciar()
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])
        self.assertFalse(Intento.objects.exists())

    def test_docente_es_enviado_a_previsualizacion(self):
        self.client.force_login(self.docente)
        r = self._iniciar()
        self.assertRedirects(
            r, f"/cuestionarios/{self.cuestionario.id}/previsualizar/", fetch_redirect_response=False,
        )
        self.assertFalse(Intento.objects.exists())

    def test_otro_estudiante_no_ve_el_intento(self):
        self._iniciar()
        intento = Intento.objects.get()
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(f"/evaluacion/{intento.id}/").status_code, 403)
        self.assertEqual(self.client.get(f"/evaluacion/{intento.id}/resultado/").status_code, 403)

    def test_intento_vencido_por_tiempo_se_cierra(self):
        self._iniciar()
        intento = Intento.objects.get()
        Intento.objects.filter(id=intento.id).update(fecha_inicio=timezone.now() - timedelta(minutes=90))
        r = self.client.get(f"/evaluacion/{intento.id}/")
        self.assertRedirects(r, f"/evaluacion/{intento.id}/resultado/", fetch_redirect_response=False)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "vencido")

    # --- Guardado automático -----------------------------------------------------

    def test_autoguardado_de_respuesta(self):
        self._iniciar()
        intento = Intento.objects.get()
        pregunta_id, opcion_id = next(iter(respuestas_correctas(self.cuestionario).items()))
        r = self.client.post(
            f"/evaluacion/{intento.id}/guardar-respuesta/",
            data=json.dumps({"pregunta_id": pregunta_id, "opcion_id": opcion_id}),
            content_type="application/json",
        )
        self.assertEqual(r.json()["status"], "ok")
        respuesta = RespuestaIntento.objects.get(intento=intento)
        self.assertTrue(respuesta.es_correcta)
        self.assertEqual(respuesta.opcion_seleccionada_id, opcion_id)

    # --- Calificación (fórmula institucional) --------------------------------------

    def test_calificacion_todas_correctas(self):
        self._iniciar()
        intento = Intento.objects.get()
        r = self._finalizar(intento, respuestas_correctas(self.cuestionario))
        self.assertRedirects(r, f"/evaluacion/{intento.id}/resultado/", fetch_redirect_response=False)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "finalizado")
        self.assertEqual(intento.puntaje_obtenido, Decimal("2.00"))
        self.assertEqual(intento.puntaje_total_posible, Decimal("2.00"))
        self.assertEqual(intento.calificacion, Decimal("5.00"))
        self.assertTrue(intento.aprobado)
        self.assertIsNotNone(intento.fecha_fin)

    def test_calificacion_parcial_reprueba(self):
        self._iniciar()
        intento = Intento.objects.get()
        self._finalizar(intento, respuestas_correctas(self.cuestionario, cuantas=1))
        intento.refresh_from_db()
        # (1 / 2) * 5.00 = 2.50 < 3.00
        self.assertEqual(intento.calificacion, Decimal("2.50"))
        self.assertFalse(intento.aprobado)

    def test_preguntas_omitidas_quedan_con_opcion_nula(self):
        self._iniciar()
        intento = Intento.objects.get()
        self._finalizar(intento, {})
        intento.refresh_from_db()
        self.assertEqual(intento.calificacion, Decimal("0.00"))
        self.assertEqual(intento.respuestas.filter(opcion_seleccionada__isnull=True).count(), 2)

    def test_resultado_muestra_revision_si_esta_permitida(self):
        self._iniciar()
        intento = Intento.objects.get()
        self._finalizar(intento, respuestas_correctas(self.cuestionario, cuantas=1))
        r = self.client.get(f"/evaluacion/{intento.id}/resultado/")
        self.assertTrue(r.context["permitir_revision"])
        self.assertEqual(len(r.context["detalles_respuestas"]), 2)
        self.assertEqual(r.context["total_correctas"], 1)

    def test_resultado_oculta_revision_si_no_esta_permitida(self):
        self.cuestionario.permitir_revision = False
        self.cuestionario.save()
        self._iniciar()
        intento = Intento.objects.get()
        self._finalizar(intento, respuestas_correctas(self.cuestionario))
        r = self.client.get(f"/evaluacion/{intento.id}/resultado/")
        self.assertFalse(r.context["permitir_revision"])
        self.assertEqual(r.context["detalles_respuestas"], [])
        self.assertNotContains(r, "Explicación de")
