"""Login, redirección por rol y control de acceso por permisos."""
from django.test import TestCase

from preguntas.tests.factories import CLAVE, crear_usuario, sembrar_roles


class AutenticacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.docente = crear_usuario("prof", "docente")
        cls.estudiante = crear_usuario("alumno", "estudiante")

    def test_login_valido_redirige_al_panel_del_rol(self):
        r = self.client.post("/login/", {"username": "prof", "password": CLAVE})
        self.assertRedirects(r, "/dashboard/docente/", fetch_redirect_response=False)
        r = self.client.get("/dashboard/docente/")
        self.assertEqual(r.status_code, 200)

    def test_login_por_correo(self):
        r = self.client.post("/login/", {"username": "alumno@uniputumayo.edu.co", "password": CLAVE})
        self.assertEqual(r.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_con_clave_incorrecta_no_autentica(self):
        r = self.client.post("/login/", {"username": "prof", "password": "otra"})
        self.assertNotEqual(r.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_inactivo_no_puede_ingresar(self):
        self.docente.is_active = False
        self.docente.save()
        self.client.post("/login/", {"username": "prof", "password": CLAVE})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_anonimo_es_enviado_al_login(self):
        r = self.client.get("/preguntas/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_estudiante_no_accede_a_modulos_docentes(self):
        self.client.force_login(self.estudiante)
        for url in ("/preguntas/", "/cuestionarios/", "/preguntas/importar/", "/usuarios/"):
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (302, 403))

    def test_docente_accede_a_sus_modulos(self):
        self.client.force_login(self.docente)
        for url in ("/preguntas/", "/cuestionarios/", "/preguntas/importar/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
