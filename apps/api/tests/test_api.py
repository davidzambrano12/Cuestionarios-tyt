"""API REST: autenticación JWT, permisos por rol y las operaciones documentadas en Swagger."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.banco_preguntas.models import Categoria
from apps.core.tests.factories import (
    CLAVE, crear_cuestionario, crear_pregunta, crear_usuario, respuestas_correctas, sembrar_roles,
)
from apps.evaluaciones.models import Intento, RespuestaIntento
from apps.evaluaciones.services import calificar_intento


class BaseAPI(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.admin = crear_usuario("jefe", "admin", is_superuser=True, is_staff=True)
        cls.docente = crear_usuario("prof", "docente")
        cls.estudiante = crear_usuario("ana", "estudiante", codigo="E1")
        cls.otro = crear_usuario("beto", "estudiante", codigo="E2")
        cls.simulacro = crear_cuestionario(num_preguntas=4, nombre="Simulacro API")

    def setUp(self):
        self.api = APIClient()

    def como(self, usuario):
        self.api.force_authenticate(usuario)
        return self.api


class AutenticacionYDocumentacionTests(BaseAPI):
    def test_swagger_y_esquema_son_publicos(self):
        self.assertEqual(self.api.get("/api/docs/").status_code, 200)
        esquema = self.api.get("/api/schema/")
        self.assertEqual(esquema.status_code, 200)
        for ruta in ("/api/simulacros/", "/api/preguntas/{id}/", "/api/intentos/", "/api/reportes/"):
            self.assertIn(ruta, esquema.content.decode())

    def test_token_jwt_da_acceso_a_la_api(self):
        token = self.api.post("/api/auth/token/", {"username": "ana", "password": CLAVE}, format="json")
        self.assertEqual(token.status_code, 200)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        respuesta = self.api.get("/api/simulacros/")
        self.assertEqual(respuesta.status_code, 200)

    def test_sin_token_responde_401(self):
        for ruta in ("/api/simulacros/", "/api/preguntas/", "/api/resultados/", "/api/reportes/"):
            self.assertEqual(self.api.get(ruta).status_code, 401, ruta)
        self.assertEqual(self.api.post("/api/intentos/", {"simulacro_id": self.simulacro.id}).status_code, 401)

    def test_token_invalido_responde_401(self):
        self.api.credentials(HTTP_AUTHORIZATION="Bearer no-es-un-token")
        self.assertEqual(self.api.get("/api/simulacros/").status_code, 401)


class SimulacrosTests(BaseAPI):
    def test_estudiante_ve_los_publicados_y_no_los_borradores(self):
        crear_cuestionario(num_preguntas=1, nombre="Borrador", estado="borrador")
        crear_cuestionario(num_preguntas=1, nombre="Cerrado", fecha_cierre=timezone.now() - timedelta(minutes=1))
        datos = self.como(self.estudiante).get("/api/simulacros/").data
        self.assertEqual([s["nombre"] for s in datos["results"]], ["Simulacro API"])
        self.assertEqual(datos["results"][0]["numero_preguntas"], 4)

    def test_docente_ve_tambien_los_borradores_institucionales(self):
        crear_cuestionario(num_preguntas=1, nombre="Borrador", estado="borrador")
        nombres = {s["nombre"] for s in self.como(self.admin).get("/api/simulacros/").data["results"]}
        self.assertEqual(nombres, {"Simulacro API", "Borrador"})


class PreguntasTests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.pregunta = self.simulacro.cuestionario_preguntas.order_by("orden").first().pregunta

    def test_docente_consulta_preguntas_con_su_clave(self):
        datos = self.como(self.docente).get("/api/preguntas/").data
        self.assertEqual(datos["count"], 4)
        self.assertIn("es_correcta", datos["results"][0]["opciones"][0])

    def test_estudiante_no_puede_consultar_el_banco(self):
        respuesta = self.como(self.estudiante).get("/api/preguntas/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("preguntas.gestionar", respuesta.data["detail"])

    def test_filtros_del_banco(self):
        otra = Categoria.objects.create(nombre="Inglés")
        crear_pregunta(otra, "Choose the correct answer")
        api = self.como(self.docente)
        self.assertEqual(api.get("/api/preguntas/", {"categoria": otra.id}).data["count"], 1)
        self.assertEqual(api.get("/api/preguntas/", {"q": "correct answer"}).data["count"], 1)

    def test_patch_del_enunciado_conserva_las_opciones_y_sus_ids(self):
        ids = list(self.pregunta.opciones.order_by("id").values_list("id", flat=True))
        respuesta = self.como(self.docente).patch(
            f"/api/preguntas/{self.pregunta.id}/", {"enunciado": "Enunciado corregido"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.pregunta.refresh_from_db()
        self.assertEqual(self.pregunta.enunciado, "Enunciado corregido")
        self.assertEqual(list(self.pregunta.opciones.order_by("id").values_list("id", flat=True)), ids)

    def test_patch_no_borra_la_respuesta_registrada(self):
        intento = Intento.objects.create(cuestionario=self.simulacro, participante_codigo="E1",
                                         participante_nombre="Ana", estado="en_progreso")
        calificar_intento(intento, respuestas_correctas(self.simulacro))
        self.como(self.docente).patch(f"/api/preguntas/{self.pregunta.id}/", {"puntaje": "2.00"}, format="json")
        respuesta = RespuestaIntento.objects.get(intento=intento, pregunta=self.pregunta)
        self.assertIsNotNone(respuesta.opcion_seleccionada_id)

    def test_patch_reemplaza_opciones_y_cambia_el_puntaje(self):
        opciones = [{"texto": f"Nueva {letra}", "es_correcta": letra == "C"} for letra in "ABC"]
        respuesta = self.como(self.docente).patch(
            f"/api/preguntas/{self.pregunta.id}/", {"opciones": opciones, "puntaje": "2.50"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([o["texto"] for o in respuesta.data["opciones"]], ["Nueva A", "Nueva B", "Nueva C"])
        self.assertEqual(Decimal(respuesta.data["puntaje"]), Decimal("2.50"))

    def test_patch_rechaza_dos_opciones_correctas(self):
        opciones = [{"texto": "Sí", "es_correcta": True}, {"texto": "No", "es_correcta": True}]
        respuesta = self.como(self.docente).patch(
            f"/api/preguntas/{self.pregunta.id}/", {"opciones": opciones}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("opciones", respuesta.data)

    def test_patch_que_duplica_otra_pregunta_responde_409(self):
        otra = self.simulacro.cuestionario_preguntas.order_by("orden")[1].pregunta
        api = self.como(self.docente)
        api.patch(f"/api/preguntas/{otra.id}/", {"puntaje": "1.00"}, format="json")  # calcula su huella
        opciones = [
            {"texto": o.texto, "es_correcta": o.es_correcta} for o in otra.opciones.order_by("orden")
        ]
        respuesta = self.como(self.docente).patch(
            f"/api/preguntas/{self.pregunta.id}/", {"enunciado": otra.enunciado, "opciones": opciones}, format="json",
        )
        self.assertEqual(respuesta.status_code, 409)

    def test_patch_desactiva_la_pregunta(self):
        self.como(self.docente).patch(f"/api/preguntas/{self.pregunta.id}/", {"activa": False}, format="json")
        self.pregunta.refresh_from_db()
        self.assertFalse(self.pregunta.activa)

    def test_estudiante_no_puede_editar_preguntas(self):
        respuesta = self.como(self.estudiante).patch(
            f"/api/preguntas/{self.pregunta.id}/", {"enunciado": "Hackeado"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.pregunta.refresh_from_db()
        self.assertNotEqual(self.pregunta.enunciado, "Hackeado")

    def test_pregunta_inexistente_responde_404(self):
        self.assertEqual(self.como(self.docente).get("/api/preguntas/999999/").status_code, 404)


class IntentosTests(BaseAPI):
    def test_estudiante_inicia_un_intento_sin_ver_las_claves(self):
        respuesta = self.como(self.estudiante).post("/api/intentos/", {"simulacro_id": self.simulacro.id}, format="json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["estado"], "en_progreso")
        self.assertEqual(len(respuesta.data["preguntas"]), 4)
        self.assertNotIn("es_correcta", respuesta.data["preguntas"][0]["opciones"][0])
        self.assertGreater(respuesta.data["segundos_restantes"], 0)
        self.assertEqual(Intento.objects.get(id=respuesta.data["id"]).participante_codigo, "E1")

    def test_iniciar_dos_veces_reanuda_el_mismo_intento(self):
        api = self.como(self.estudiante)
        primero = api.post("/api/intentos/", {"simulacro_id": self.simulacro.id}, format="json")
        segundo = api.post("/api/intentos/", {"simulacro_id": self.simulacro.id}, format="json")
        self.assertEqual(segundo.status_code, 200)
        self.assertEqual(primero.data["id"], segundo.data["id"])

    def test_iniciar_con_respuestas_califica_con_la_formula_institucional(self):
        respuestas = respuestas_correctas(self.simulacro, cuantas=3)  # 3 de 4 → 3,75 / 5,00
        respuesta = self.como(self.estudiante).post(
            "/api/intentos/", {"simulacro_id": self.simulacro.id, "respuestas": respuestas}, format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["estado"], "finalizado")
        self.assertEqual(Decimal(respuesta.data["calificacion"]), Decimal("3.75"))
        self.assertTrue(respuesta.data["aprobado"])
        self.assertEqual(respuesta.data["preguntas"], [])

    def test_entregar_un_intento_en_curso(self):
        api = self.como(self.estudiante)
        intento_id = api.post("/api/intentos/", {"simulacro_id": self.simulacro.id}, format="json").data["id"]
        respuesta = api.post(
            f"/api/intentos/{intento_id}/finalizar/",
            {"respuestas": respuestas_correctas(self.simulacro, cuantas=1)}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Decimal(respuesta.data["calificacion"]), Decimal("1.25"))
        self.assertEqual(respuesta.data["dictamen"], "Reprobado")
        repetido = api.post(f"/api/intentos/{intento_id}/finalizar/", {"respuestas": {}}, format="json")
        self.assertEqual(repetido.status_code, 409)

    def test_no_se_entrega_el_intento_de_otro_estudiante(self):
        intento_id = self.como(self.estudiante).post(
            "/api/intentos/", {"simulacro_id": self.simulacro.id}, format="json",
        ).data["id"]
        respuesta = self.como(self.otro).post(f"/api/intentos/{intento_id}/finalizar/", {"respuestas": {}}, format="json")
        self.assertEqual(respuesta.status_code, 403)

    def test_entregar_fuera_de_tiempo_cierra_como_vencido(self):
        api = self.como(self.estudiante)
        intento_id = api.post("/api/intentos/", {"simulacro_id": self.simulacro.id}, format="json").data["id"]
        Intento.objects.filter(id=intento_id).update(fecha_inicio=timezone.now() - timedelta(minutes=90))
        respuesta = api.post(f"/api/intentos/{intento_id}/finalizar/", {"respuestas": {}}, format="json")
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(Intento.objects.get(id=intento_id).estado, "vencido")

    def test_limite_de_intentos(self):
        api = self.como(self.estudiante)
        for _ in range(self.simulacro.intentos_permitidos):
            api.post("/api/intentos/", {"simulacro_id": self.simulacro.id, "respuestas": {}}, format="json")
        respuesta = api.post("/api/intentos/", {"simulacro_id": self.simulacro.id}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("límite", respuesta.data["detail"])

    def test_simulacro_no_publicado_se_rechaza(self):
        borrador = crear_cuestionario(num_preguntas=1, estado="borrador")
        respuesta = self.como(self.estudiante).post("/api/intentos/", {"simulacro_id": borrador.id}, format="json")
        self.assertEqual(respuesta.status_code, 400)

    def test_simulacro_inexistente_responde_404(self):
        respuesta = self.como(self.estudiante).post("/api/intentos/", {"simulacro_id": 999999}, format="json")
        self.assertEqual(respuesta.status_code, 404)

    def test_docente_no_registra_intentos(self):
        respuesta = self.como(self.docente).post("/api/intentos/", {"simulacro_id": self.simulacro.id}, format="json")
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Intento.objects.exists())


class ResultadosYReportesTests(BaseAPI):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        hoy = timezone.localdate()
        cls.periodo = PeriodoAcademico.objects.create(
            anio=hoy.year, numero=2, fecha_inicio=hoy - timedelta(days=30), fecha_fin=hoy + timedelta(days=30),
        )
        cls.viejo = PeriodoAcademico.objects.create(anio=2020, numero=1, fecha_inicio=date(2020, 2, 1), fecha_fin=date(2020, 6, 30))
        cls.curso = Curso.objects.create(periodo=cls.periodo, asignatura="Frameworks", grupo="01", semestre=6, docente=cls.docente)
        cls.ajeno = Curso.objects.create(periodo=cls.periodo, asignatura="Redes", grupo="01", semestre=6, docente=cls.admin)
        Matricula.objects.create(estudiante=cls.estudiante, curso=cls.curso)
        Matricula.objects.create(estudiante=cls.otro, curso=cls.ajeno)
        for est, curso, correctas in ((cls.estudiante, cls.curso, 4), (cls.otro, cls.ajeno, 2)):
            intento = Intento.objects.create(
                cuestionario=cls.simulacro, curso=curso, periodo=curso.periodo, estado="en_progreso",
                participante_nombre=est.get_full_name(), participante_codigo=est.perfil.codigo_institucional,
            )
            calificar_intento(intento, respuestas_correctas(cls.simulacro, cuantas=correctas))

    def test_estudiante_solo_ve_sus_resultados(self):
        datos = self.como(self.estudiante).get("/api/resultados/").data
        self.assertEqual(datos["count"], 1)
        self.assertEqual(datos["results"][0]["participante_codigo"], "E1")
        self.assertEqual(datos["results"][0]["curso"], "Frameworks · G01")

    def test_docente_ve_los_resultados_de_sus_cursos(self):
        datos = self.como(self.docente).get("/api/resultados/").data
        self.assertEqual([r["participante_codigo"] for r in datos["results"]], ["E1"])

    def test_admin_ve_todos_los_resultados(self):
        self.assertEqual(self.como(self.admin).get("/api/resultados/").data["count"], 2)

    def test_reporte_filtrado_por_anio_curso_y_eje(self):
        eje = Categoria.objects.get(nombre="Razonamiento Cuantitativo")
        datos = self.como(self.admin).get("/api/reportes/", {
            "anio": self.periodo.anio, "curso": self.curso.id, "eje": eje.id,
        }).data
        self.assertEqual(datos["indicadores"]["intentos"], 1)
        self.assertEqual(Decimal(datos["indicadores"]["promedio"]), Decimal("5.00"))
        self.assertEqual(datos["por_curso"][0]["curso"], "Frameworks · G01")
        self.assertEqual(datos["por_eje"][0]["eje"], "Razonamiento Cuantitativo")
        self.assertIn({"filtro": "Curso", "valor": "Frameworks · G01"}, datos["filtros"])

    def test_reporte_sin_filtros_promedia_todo(self):
        datos = self.como(self.admin).get("/api/reportes/").data
        self.assertEqual(datos["indicadores"]["intentos"], 2)
        self.assertEqual(Decimal(datos["indicadores"]["promedio"]), Decimal("3.75"))

    def test_filtro_incompatible_se_quita_con_aviso(self):
        datos = self.como(self.admin).get("/api/reportes/", {"anio": 2020, "curso": self.curso.id}).data
        self.assertTrue(datos["avisos"])
        self.assertEqual(datos["indicadores"]["intentos"], 0)

    def test_docente_no_puede_pedir_un_curso_ajeno(self):
        respuesta = self.como(self.docente).get("/api/reportes/", {"curso": self.ajeno.id})
        self.assertEqual(respuesta.status_code, 403)

    def test_estudiante_no_accede_a_reportes(self):
        self.assertEqual(self.como(self.estudiante).get("/api/reportes/").status_code, 403)
