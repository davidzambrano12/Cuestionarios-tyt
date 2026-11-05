"""Cuestionarios institucionales y de curso: quién los edita, quién los presenta y en qué curso cuentan."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.core.models import PermisoSistema
from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles
from apps.cuestionarios.models import Cuestionario
from apps.evaluaciones.models import Intento


class VisibilidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.admin = crear_usuario("jefe", "admin", is_superuser=True, is_staff=True)
        cls.docente = crear_usuario("prof", "docente")
        cls.otro = crear_usuario("otra", "docente")
        cls.ana = crear_usuario("ana", "estudiante", codigo="E1")
        cls.beto = crear_usuario("beto", "estudiante", codigo="E2")
        hoy = timezone.localdate()
        cls.periodo = PeriodoAcademico.objects.create(anio=hoy.year, numero=2, fecha_inicio=hoy - timedelta(days=30),
                                                      fecha_fin=hoy + timedelta(days=30))
        cls.mio = Curso.objects.create(periodo=cls.periodo, asignatura="Frameworks", grupo="01", docente=cls.docente)
        cls.mio2 = Curso.objects.create(periodo=cls.periodo, asignatura="Bases de Datos", grupo="01", docente=cls.docente)
        cls.ajeno = Curso.objects.create(periodo=cls.periodo, asignatura="Frameworks", grupo="02", docente=cls.otro)
        Matricula.objects.create(curso=cls.mio, estudiante=cls.ana)
        Matricula.objects.create(curso=cls.mio2, estudiante=cls.ana)
        Matricula.objects.create(curso=cls.ajeno, estudiante=cls.beto)

        cls.institucional = crear_cuestionario(num_preguntas=1, nombre="Simulacro institucional")
        cls.privado = crear_cuestionario(num_preguntas=1, nombre="Parcial Frameworks", visibilidad="privado",
                                         creado_por=cls.docente)
        cls.privado.cursos.set([cls.mio])
        cls.de_otro = crear_cuestionario(num_preguntas=1, nombre="Parcial de otra", visibilidad="privado",
                                         creado_por=cls.otro)
        cls.de_otro.cursos.set([cls.ajeno])

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def datos(self, **extra):
        base = {
            "nombre": "Nuevo", "descripcion": "x", "tiempo_limite_minutos": "30", "intentos_permitidos": "2",
            "fecha_apertura": "2026-01-01T08:00", "fecha_cierre": "2026-12-31T18:00",
            "calificacion_maxima": "5", "calificacion_aprobacion": "3",
            "preguntas_ids": [str(self.institucional.cuestionario_preguntas.first().pregunta_id)],
        }
        base.update(extra)
        return base

    # --- Edición ---------------------------------------------------------------

    def test_docente_crea_de_curso_a_su_nombre(self):
        self.entrar(self.docente)
        self.client.post("/cuestionarios/crear/", self.datos(visibilidad="privado", cursos=[self.mio.id], accion="publicar"))
        nuevo = Cuestionario.objects.get(nombre="Nuevo")
        self.assertEqual((nuevo.creado_por, nuevo.visibilidad, nuevo.estado), (self.docente, "privado", "disponible"))
        self.assertEqual(list(nuevo.cursos.all()), [self.mio])

    def test_docente_no_publica_institucional(self):
        self.entrar(self.docente)
        r = self.client.post("/cuestionarios/crear/", self.datos(visibilidad="institucional"))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Cuestionario.objects.filter(nombre="Nuevo").exists())

    def test_con_permiso_publica_institucional(self):
        self.docente.perfil.rol.permisos.add(PermisoSistema.objects.get(codigo="cuestionarios.publicar"))
        self.entrar(self.docente)
        self.client.post("/cuestionarios/crear/", self.datos(visibilidad="institucional", cursos=[self.mio.id]))
        nuevo = Cuestionario.objects.get(nombre="Nuevo")
        self.assertEqual(nuevo.visibilidad, "institucional")
        self.assertFalse(nuevo.cursos.exists())  # un institucional no lleva cursos

    def test_no_asigna_cursos_ajenos(self):
        self.entrar(self.docente)
        r = self.client.post("/cuestionarios/crear/", self.datos(visibilidad="privado", cursos=[self.ajeno.id]))
        self.assertEqual(r.status_code, 400)

    def test_publicar_de_curso_exige_un_curso(self):
        self.entrar(self.docente)
        r = self.client.post("/cuestionarios/crear/", self.datos(visibilidad="privado", accion="publicar"))
        self.assertEqual(r.status_code, 400)

    def test_docente_solo_edita_los_suyos(self):
        self.entrar(self.docente)
        for c, esperado in ((self.privado, 200), (self.de_otro, 403), (self.institucional, 403)):
            with self.subTest(c.nombre):
                self.assertEqual(self.client.get(f"/cuestionarios/{c.id}/editar/").status_code, esperado)
                self.assertEqual(self.client.get(f"/cuestionarios/{c.id}/intentos/").status_code, esperado)
        self.assertEqual(self.client.get(f"/cuestionarios/{self.de_otro.id}/previsualizar/").status_code, 403)
        self.assertEqual(self.client.get(f"/cuestionarios/{self.institucional.id}/previsualizar/").status_code, 200)
        listado = {c.nombre for c in self.client.get("/cuestionarios/").context["cuestionarios"]}
        self.assertEqual(listado, {"Simulacro institucional", "Parcial Frameworks"})

    def test_se_conservan_los_cursos_asignados_por_otra_persona(self):
        self.privado.cursos.add(self.ajeno)  # p. ej. lo agregó un administrador
        self.entrar(self.docente)
        self.client.post(f"/cuestionarios/{self.privado.id}/editar/",
                         self.datos(nombre="Parcial Frameworks", visibilidad="privado", cursos=[self.mio2.id]))
        self.assertEqual(set(self.privado.cursos.values_list("id", flat=True)), {self.mio2.id, self.ajeno.id})

    def test_admin_edita_cualquiera(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get(f"/cuestionarios/{self.de_otro.id}/editar/").status_code, 200)

    # --- Estudiantes -----------------------------------------------------------

    def test_estudiante_ve_institucionales_y_los_de_sus_cursos(self):
        self.entrar(self.ana)
        nombres = {c.nombre for c in self.client.get("/dashboard/estudiante/").context["cuestionarios_disponibles"]}
        self.assertEqual(nombres, {"Simulacro institucional", "Parcial Frameworks"})
        self.entrar(self.beto)
        nombres = {c.nombre for c in self.client.get("/dashboard/estudiante/").context["cuestionarios_disponibles"]}
        self.assertEqual(nombres, {"Simulacro institucional", "Parcial de otra"})

    def test_no_presenta_uno_de_curso_ajeno_por_url(self):
        self.entrar(self.beto)
        r = self.client.get(f"/evaluacion/iniciar/{self.privado.id}/")
        self.assertRedirects(r, "/dashboard/estudiante/", fetch_redirect_response=False)
        self.assertFalse(Intento.objects.exists())

    def test_de_curso_cuenta_en_su_curso(self):
        self.entrar(self.ana)
        self.client.get(f"/evaluacion/iniciar/{self.privado.id}/")
        intento = Intento.objects.get()
        self.assertEqual((intento.curso, intento.periodo), (self.mio, self.periodo))

    def test_institucional_con_varios_cursos_pide_elegir(self):
        self.entrar(self.ana)
        r = self.client.get(f"/evaluacion/iniciar/{self.institucional.id}/")
        self.assertTemplateUsed(r, "evaluaciones/elegir_curso.html")
        self.assertEqual({c.id for c in r.context["cursos"]}, {self.mio.id, self.mio2.id})
        self.assertFalse(Intento.objects.exists())
        # Un curso que no es suyo no vale
        r = self.client.post(f"/evaluacion/iniciar/{self.institucional.id}/", {"curso": self.ajeno.id})
        self.assertTemplateUsed(r, "evaluaciones/elegir_curso.html")
        r = self.client.post(f"/evaluacion/iniciar/{self.institucional.id}/", {"curso": self.mio2.id})
        intento = Intento.objects.get()
        self.assertRedirects(r, f"/evaluacion/{intento.id}/", fetch_redirect_response=False)
        self.assertEqual(intento.curso, self.mio2)
        # Al volver a entrar se reanuda, sin preguntar de nuevo
        r = self.client.get(f"/evaluacion/iniciar/{self.institucional.id}/")
        self.assertRedirects(r, f"/evaluacion/{intento.id}/", fetch_redirect_response=False)

    def test_institucional_con_un_curso_no_pregunta(self):
        self.entrar(self.beto)
        self.client.get(f"/evaluacion/iniciar/{self.institucional.id}/")
        self.assertEqual(Intento.objects.get().curso, self.ajeno)

    def test_institucional_sin_matricula_queda_en_su_periodo(self):
        self.entrar(crear_usuario("caro", "estudiante", codigo="E3"))
        self.client.get(f"/evaluacion/iniciar/{self.institucional.id}/")
        intento = Intento.objects.get()
        self.assertEqual((intento.curso, intento.periodo), (None, self.periodo))

    def test_portada_solo_anuncia_institucionales(self):
        nombres = {c.nombre for c in self.client.get("/").context["cuestionarios"]}
        self.assertEqual(nombres, {"Simulacro institucional"})
