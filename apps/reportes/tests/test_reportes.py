"""Reporte de intentos (CU-05), métricas y exportación a Excel."""
import io
from decimal import Decimal

from django.test import TestCase
from openpyxl import load_workbook

from apps.evaluaciones.models import Intento
from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles


class ReportesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.docente = crear_usuario("prof", "docente")
        cls.estudiante = crear_usuario("alumno", "estudiante", codigo="EST-001")
        cls.cuestionario = crear_cuestionario(num_preguntas=2, visibilidad="privado", creado_por=cls.docente)

        def intento(codigo, nombre, estado, calificacion=None):
            return Intento.objects.create(
                cuestionario=cls.cuestionario, participante_codigo=codigo,
                participante_nombre=nombre, estado=estado, calificacion=calificacion,
                aprobado=(calificacion >= Decimal("3.00")) if calificacion is not None else None,
                duracion_segundos=600 if estado != "en_progreso" else None,
            )

        # Ana: reprobó y luego aprobó -> nota definitiva 4.00
        intento("EST-001", "Ana Gómez", "finalizado", Decimal("2.00"))
        cls.intento_ana = intento("EST-001", "Ana Gómez", "finalizado", Decimal("4.00"))
        # Beto: reprobó
        intento("EST-002", "Beto Ruiz", "finalizado", Decimal("1.50"))
        # Caro: solo intentos sin nota (vencido + en curso) -> no cuenta como reprobada
        intento("EST-003", "Caro Paz", "vencido")
        intento("EST-003", "Caro Paz", "en_progreso")

    def setUp(self):
        self.client.force_login(self.docente)

    def test_metricas_del_reporte(self):
        r = self.client.get(f"/cuestionarios/{self.cuestionario.id}/intentos/")
        ctx = r.context
        self.assertEqual(ctx["total_estudiantes"], 3)
        self.assertEqual(ctx["estudiantes_aprobados_count"], 1)
        self.assertEqual(ctx["estudiantes_reprobados_count"], 1)
        self.assertEqual(ctx["estudiantes_sin_nota_count"], 1)
        self.assertEqual(ctx["tasa_aprobacion"], 50.0)
        # Promedio de notas definitivas: (4.00 + 1.50) / 2
        self.assertEqual(ctx["promedio_calif"], Decimal("2.75"))
        ana = next(e for e in ctx["estudiantes_agrupados"] if e["codigo"] == "EST-001")
        self.assertEqual(ana["mejor_calificacion"], Decimal("4.00"))
        self.assertEqual(ana["total_intentos"], 2)

    def test_exportacion_excel(self):
        r = self.client.get(f"/cuestionarios/{self.cuestionario.id}/intentos/exportar/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        wb = load_workbook(io.BytesIO(r.content))
        self.assertEqual(wb.sheetnames, ["Resumen", "Notas definitivas", "Historial de intentos"])

        notas = {fila[0]: fila for fila in wb["Notas definitivas"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(notas["EST-001"][4], 4)
        self.assertEqual(notas["EST-001"][6], "Aprobado")
        self.assertEqual(notas["EST-002"][6], "Reprobado")
        self.assertIn(notas["EST-003"][6], ("En curso", "Sin nota"))

        dictamenes = [fila[10] for fila in wb["Historial de intentos"].iter_rows(min_row=2, values_only=True)]
        self.assertEqual(len(dictamenes), 5)
        self.assertIn("Vencido sin calificar", dictamenes)

    def test_exportacion_respeta_la_busqueda(self):
        r = self.client.get(f"/cuestionarios/{self.cuestionario.id}/intentos/exportar/?q=beto")
        wb = load_workbook(io.BytesIO(r.content))
        codigos = [f[0] for f in wb["Notas definitivas"].iter_rows(min_row=2, values_only=True)]
        self.assertEqual(codigos, ["EST-002"])

    def test_docente_audita_el_resultado_de_un_estudiante(self):
        r = self.client.get(f"/evaluacion/{self.intento_ana.id}/resultado/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["es_auditor"])

    def test_estudiante_no_accede_al_reporte_ni_a_la_exportacion(self):
        self.client.force_login(self.estudiante)
        base = f"/cuestionarios/{self.cuestionario.id}/intentos/"
        self.assertEqual(self.client.get(base).status_code, 403)
        self.assertEqual(self.client.get(base + "exportar/").status_code, 403)

    def test_estudiante_ve_su_propio_resultado(self):
        self.client.force_login(self.estudiante)
        r = self.client.get(f"/evaluacion/{self.intento_ana.id}/resultado/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["es_auditor"])
