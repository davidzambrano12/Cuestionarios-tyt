"""Gestión de períodos académicos: validaciones, edición y eliminación protegida."""
from datetime import date, datetime

from django.test import TestCase
from django.utils import timezone

from apps.academico.forms import PeriodoForm
from apps.academico.models import Curso, PeriodoAcademico
from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles
from apps.evaluaciones.models import Intento


def _datos(anio=2027, numero=1, inicio="2027-02-01", fin="2027-06-15"):
    return {"anio": anio, "numero": numero, "fecha_inicio": inicio, "fecha_fin": fin}


class ValidacionPeriodoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.p2026_2 = PeriodoAcademico.objects.create(anio=2026, numero=2, fecha_inicio=date(2026, 7, 15), fecha_fin=date(2026, 12, 10))

    def _errores(self, **datos):
        form = PeriodoForm(_datos(**datos))
        form.is_valid()
        return " ".join(e for lista in form.errors.values() for e in lista)

    def test_periodo_valido(self):
        self.assertTrue(PeriodoForm(_datos()).is_valid())

    def test_el_anio_debe_coincidir_con_la_fecha_de_inicio(self):
        # El caso real: «2000-2» con fechas de noviembre de 2026
        self.assertIn("debe empezar en 2000", self._errores(anio=2000, numero=2, inicio="2026-11-27", fin="2026-11-28"))

    def test_no_se_cruza_con_otro_periodo(self):
        self.assertIn("se cruzan con el período 2026-2", self._errores(anio=2026, numero=3, inicio="2026-12-01", fin="2026-12-20"))

    def test_fin_posterior_al_inicio(self):
        self.assertIn("posterior", self._errores(inicio="2027-06-15", fin="2027-02-01"))

    def test_no_repite_anio_y_numero(self):
        self.assertTrue(self._errores(anio=2026, numero=2, inicio="2026-01-01", fin="2026-01-31"))


class GestionPeriodosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.admin = crear_usuario("jefe", "admin", is_superuser=True, is_staff=True)
        cls.docente = crear_usuario("prof", "docente")
        cls.vacio = PeriodoAcademico.objects.create(anio=2027, numero=1, fecha_inicio=date(2027, 2, 1), fecha_fin=date(2027, 6, 15))
        cls.usado = PeriodoAcademico.objects.create(anio=2026, numero=2, fecha_inicio=date(2026, 7, 15), fecha_fin=date(2026, 12, 10))
        Curso.objects.create(periodo=cls.usado, asignatura="Electiva", grupo="01", docente=cls.docente)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_solo_el_administrador_ve_y_cambia_periodos(self):
        self.client.force_login(self.docente)
        self.assertEqual(self.client.get("/cursos/periodos/").status_code, 403)
        self.assertEqual(self.client.post(f"/cursos/periodos/{self.vacio.id}/eliminar/").status_code, 403)
        self.assertTrue(PeriodoAcademico.objects.filter(id=self.vacio.id).exists())

    def test_listado_muestra_el_uso(self):
        r = self.client.get("/cursos/periodos/")
        uso = {p.id: (p.n_cursos, p.n_intentos) for p in r.context["periodos"]}
        self.assertEqual(uso[self.usado.id], (1, 0))
        self.assertEqual(uso[self.vacio.id], (0, 0))

    def test_elimina_un_periodo_vacio(self):
        self.client.post(f"/cursos/periodos/{self.vacio.id}/eliminar/")
        self.assertFalse(PeriodoAcademico.objects.filter(id=self.vacio.id).exists())

    def test_no_elimina_un_periodo_con_cursos(self):
        r = self.client.post(f"/cursos/periodos/{self.usado.id}/eliminar/", follow=True)
        self.assertContains(r, "no se puede eliminar")
        self.assertTrue(PeriodoAcademico.objects.filter(id=self.usado.id).exists())

    def test_corrige_un_periodo_vacio(self):
        self.client.post(f"/cursos/periodos/{self.vacio.id}/editar/", _datos(anio=2027, numero=2, inicio="2027-07-15", fin="2027-12-10"))
        self.vacio.refresh_from_db()
        self.assertEqual((self.vacio.numero, self.vacio.fecha_inicio), (2, date(2027, 7, 15)))

    def test_con_historial_solo_cambian_las_fechas(self):
        self.client.post(f"/cursos/periodos/{self.usado.id}/editar/", _datos(anio=2026, numero=1, inicio="2026-07-01", fin="2026-12-15"))
        self.usado.refresh_from_db()
        self.assertEqual(self.usado.numero, 2)  # el número se ignora
        self.assertEqual(self.usado.fecha_inicio, date(2026, 7, 1))

    def test_las_fechas_deben_incluir_sus_intentos(self):
        intento = Intento.objects.create(
            cuestionario=crear_cuestionario(), periodo=self.usado,
            participante_nombre="Ana", participante_codigo="E1",
        )
        Intento.objects.filter(id=intento.id).update(
            fecha_inicio=timezone.make_aware(datetime(2026, 11, 20, 10, 0)),
        )
        r = self.client.post(f"/cursos/periodos/{self.usado.id}/editar/", _datos(anio=2026, numero=2, inicio="2026-07-15", fin="2026-11-01"), follow=True)
        self.assertContains(r, "deben incluirlos")
        self.usado.refresh_from_db()
        self.assertEqual(self.usado.fecha_fin, date(2026, 12, 10))

    def test_el_listado_de_cursos_agrupa_por_periodo(self):
        r = self.client.get("/cursos/")
        self.assertContains(r, 'class="fila-periodo"')
        self.assertContains(r, "Grupo 01")
        self.assertContains(r, "/cursos/periodos/")
