"""Cursos y matrículas: permisos por rol, matrícula, retiro y asignación de intentos."""
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles
from apps.evaluaciones.models import Intento


class CursosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.admin = crear_usuario("jefe", "admin", is_superuser=True, is_staff=True)
        cls.docente = crear_usuario("prof", "docente")
        cls.otro = crear_usuario("otra", "docente")
        cls.ana = crear_usuario("ana", "estudiante", codigo="E1", first_name="Ana", last_name="Gómez")
        cls.beto = crear_usuario("beto", "estudiante", codigo="E2", first_name="Beto", last_name="Ruiz")
        cls.periodo = PeriodoAcademico.objects.create(anio=2026, numero=2, fecha_inicio=date(2026, 7, 1), fecha_fin=date(2026, 12, 15))
        cls.curso = Curso.objects.create(periodo=cls.periodo, asignatura="Electiva Profesional III", grupo="01", docente=cls.docente)
        cls.ajeno = Curso.objects.create(periodo=cls.periodo, asignatura="Electiva Profesional III", grupo="02", docente=cls.otro)

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def test_nombre_universitario(self):
        self.assertEqual(self.curso.nombre, "Electiva Profesional III · G01")
        self.assertEqual(str(self.curso), "Electiva Profesional III · G01 (2026-2)")

    def test_docente_solo_ve_y_gestiona_sus_cursos(self):
        self.entrar(self.docente)
        r = self.client.get("/cursos/")
        self.assertEqual([c.id for c in r.context["cursos"]], [self.curso.id])
        self.assertEqual(self.client.get(f"/cursos/{self.ajeno.id}/").status_code, 403)
        self.assertEqual(self.client.post(f"/cursos/{self.ajeno.id}/matricular/", {"estudiantes": [self.ana.id]}).status_code, 403)
        self.assertFalse(Matricula.objects.exists())

    def test_estudiante_no_accede(self):
        self.entrar(self.ana)
        self.assertEqual(self.client.get("/cursos/").status_code, 403)

    def test_docente_crea_curso_a_su_cargo(self):
        self.entrar(self.docente)
        r = self.client.post("/cursos/nuevo/", {
            "periodo": self.periodo.id, "asignatura": "Ingeniería de Software II", "grupo": "01",
            "programa": "Ingeniería de Sistemas", "semestre": 6, "docente": self.otro.id, "activo": "on",
        })
        curso = Curso.objects.get(asignatura="Ingeniería de Software II")
        self.assertRedirects(r, f"/cursos/{curso.id}/")
        self.assertEqual(curso.docente, self.docente)  # no puede asignarlo a otro docente

    def test_grupo_duplicado_en_el_periodo(self):
        self.entrar(self.admin)
        r = self.client.post("/cursos/nuevo/", {
            "periodo": self.periodo.id, "asignatura": "Electiva Profesional III", "grupo": "01",
            "programa": "Ingeniería de Sistemas", "activo": "on",
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)

    def test_solo_admin_crea_periodos(self):
        datos = {"anio": 2027, "numero": 1, "fecha_inicio": "2027-02-01", "fecha_fin": "2027-06-15"}
        self.entrar(self.docente)
        self.assertEqual(self.client.post("/cursos/periodos/nuevo/", datos).status_code, 403)
        self.entrar(self.admin)
        self.client.post("/cursos/periodos/nuevo/", datos)
        self.assertTrue(PeriodoAcademico.objects.filter(anio=2027, numero=1).exists())
        self.client.post("/cursos/periodos/nuevo/", {**datos, "numero": 2, "fecha_fin": "2027-01-01"})
        self.assertFalse(PeriodoAcademico.objects.filter(anio=2027, numero=2).exists())  # fin antes del inicio

    def buscar(self, q):
        return self.client.get(f"/cursos/{self.curso.id}/buscar-estudiantes/", {"q": q}).json()["resultados"]

    def test_busqueda_en_vivo_y_matricular_varios(self):
        self.entrar(self.docente)
        self.assertEqual(self.buscar("A"), [])  # menos de 2 letras: no consulta
        self.assertEqual([e["id"] for e in self.buscar("Gómez")], [self.ana.id])
        self.assertEqual([e["id"] for e in self.buscar("ruiz")], [self.beto.id])
        # «Prueba» es el apellido de los docentes y el administrador de prueba: no son estudiantes
        self.assertFalse({self.docente.id, self.otro.id, self.admin.id} & {e["id"] for e in self.buscar("Prueba")})
        self.assertEqual(self.buscar("E1")[0]["codigo"], "E1")  # también por código
        self.client.post(f"/cursos/{self.curso.id}/matricular/", {"estudiantes": [self.ana.id, self.beto.id, self.otro.id]})
        self.assertEqual(set(self.curso.matriculas.values_list("estudiante_id", flat=True)), {self.ana.id, self.beto.id})
        self.assertEqual(self.buscar("Ana"), [])  # ya matriculada: no se ofrece

    def test_busqueda_avisa_otro_curso_del_periodo(self):
        Matricula.objects.create(curso=self.ajeno, estudiante=self.ana)
        self.entrar(self.admin)
        self.assertEqual(self.buscar("Ana")[0]["otro_curso"], "Electiva Profesional III")

    def test_revisar_lista_de_codigos(self):
        Matricula.objects.create(curso=self.curso, estudiante=self.beto)
        self.entrar(self.docente)
        r = self.client.post(f"/cursos/{self.curso.id}/revisar-codigos/",
                             {"codigos": "E1\nE2, NOEXISTE ;E1\n\n  COD-PROF"}).json()
        self.assertEqual([e["codigo"] for e in r["encontrados"]], ["E1"])  # sin repetir
        self.assertEqual(r["ya_matriculados"], ["E2"])
        self.assertEqual(r["no_existen"], ["NOEXISTE", "COD-PROF"])  # un docente no es estudiante
        self.assertFalse(Matricula.objects.filter(estudiante=self.ana).exists())  # revisar no matricula

    def test_rutas_nuevas_respetan_el_curso_del_docente(self):
        self.entrar(self.docente)
        self.assertEqual(self.client.get(f"/cursos/{self.ajeno.id}/buscar-estudiantes/", {"q": "Ana"}).status_code, 403)
        self.assertEqual(self.client.post(f"/cursos/{self.ajeno.id}/revisar-codigos/", {"codigos": "E1"}).status_code, 403)
        self.entrar(self.ana)
        self.assertEqual(self.client.get(f"/cursos/{self.curso.id}/buscar-estudiantes/", {"q": "Ana"}).status_code, 403)

    def test_curso_inactivo_no_admite_matriculas(self):
        Curso.objects.filter(id=self.curso.id).update(activo=False)
        self.entrar(self.docente)
        self.client.post(f"/cursos/{self.curso.id}/matricular/", {"estudiantes": [self.ana.id]})
        self.assertFalse(Matricula.objects.exists())
        self.assertNotContains(self.client.get(f"/cursos/{self.curso.id}/"), 'id="modal-matricular"')

    def test_detalle_resume_intentos_y_ultima_nota(self):
        from decimal import Decimal
        Matricula.objects.create(curso=self.curso, estudiante=self.ana)
        Matricula.objects.create(curso=self.curso, estudiante=self.beto)
        simulacro = crear_cuestionario(num_preguntas=1)
        for nota in ("2.00", "4.50"):
            Intento.objects.create(cuestionario=simulacro, curso=self.curso, participante_codigo="E1",
                                   participante_nombre="Ana", estado="finalizado", calificacion=Decimal(nota))
        self.entrar(self.docente)
        r = self.client.get(f"/cursos/{self.curso.id}/")
        self.assertEqual(r.context["resumen"], {"total": 2, "con_intentos": 1, "sin_intentos": 1})
        ana = next(m for m in r.context["matriculas"] if m.estudiante == self.ana)
        self.assertEqual((ana.num_intentos, ana.ultima_nota), (2, Decimal("4.50")))
        self.assertContains(r, "estudiante=E1")  # enlace al historial en Consultas

    def test_matricular_asocia_intentos_anteriores_del_periodo(self):
        simulacro = crear_cuestionario(num_preguntas=1)
        dentro = Intento.objects.create(cuestionario=simulacro, participante_codigo="E1", participante_nombre="Ana", estado="finalizado")
        fuera = Intento.objects.create(cuestionario=simulacro, participante_codigo="E1", participante_nombre="Ana", estado="finalizado")
        Intento.objects.filter(id=dentro.id).update(fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 3, 9)))
        Intento.objects.filter(id=fuera.id).update(fecha_inicio=timezone.make_aware(timezone.datetime(2026, 3, 3, 9)))
        self.entrar(self.admin)
        self.client.get("/cursos/")  # el aviso cuenta los intentos sin curso
        self.assertEqual(self.client.get("/cursos/").context["sin_curso"]["intentos"], 2)
        self.client.post(f"/cursos/{self.curso.id}/matricular/", {"estudiantes": [self.ana.id]})
        dentro.refresh_from_db(); fuera.refresh_from_db()
        self.assertEqual(dentro.curso, self.curso)
        self.assertIsNone(fuera.curso)  # de otro período

    def test_aviso_de_otro_curso_en_el_mismo_periodo(self):
        Matricula.objects.create(curso=self.ajeno, estudiante=self.ana)
        self.entrar(self.admin)
        r = self.client.post(f"/cursos/{self.curso.id}/matricular/", {"estudiantes": [self.ana.id]}, follow=True)
        self.assertContains(r, "ya está(n) en otro curso de 2026-2")

    def test_retirar_sin_intentos(self):
        m = Matricula.objects.create(curso=self.curso, estudiante=self.ana)
        self.entrar(self.docente)
        self.client.post(f"/cursos/{self.curso.id}/retirar/{m.id}/")
        self.assertFalse(Matricula.objects.filter(id=m.id).exists())

    def test_no_se_retira_a_quien_tiene_historial(self):
        m = Matricula.objects.create(curso=self.curso, estudiante=self.ana)
        Intento.objects.create(cuestionario=crear_cuestionario(num_preguntas=1), curso=self.curso,
                               participante_codigo="E1", participante_nombre="Ana", estado="finalizado")
        self.entrar(self.docente)
        r = self.client.post(f"/cursos/{self.curso.id}/retirar/{m.id}/", follow=True)
        self.assertTrue(Matricula.objects.filter(id=m.id).exists())
        self.assertContains(r, "historial debe conservarse")

    def test_retirar_matricula_de_otro_curso_por_url(self):
        m = Matricula.objects.create(curso=self.ajeno, estudiante=self.ana)
        self.entrar(self.docente)
        self.assertEqual(self.client.post(f"/cursos/{self.curso.id}/retirar/{m.id}/").status_code, 404)
        self.assertTrue(Matricula.objects.filter(id=m.id).exists())
