"""
Renderizado de todas las páginas por rol: detecta templates rotos
(p. ej. un `{% url %}` con nombre o argumentos incorrectos).
"""
import json
from decimal import Decimal

from django.test import TestCase

from apps.evaluaciones.models import Intento
from apps.core.tests.factories import (
    CLAVE,
    crear_cuestionario,
    crear_usuario,
    respuestas_correctas,
    sembrar_roles,
)


class PaginasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.docente = crear_usuario("prof", "docente")
        cls.admin = crear_usuario("jefe", "admin", is_superuser=True, is_staff=True)
        cls.estudiante = crear_usuario("alumno", "estudiante", codigo="EST-001")
        cls.cuestionario = crear_cuestionario(num_preguntas=2)

    def _ok(self, user, urls):
        self.client.force_login(user)
        for url in urls:
            with self.subTest(usuario=user.username, url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_paginas_publicas(self):
        for url in ("/", "/login/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_paginas_docente(self):
        cid = self.cuestionario.id
        self._ok(self.docente, [
            "/dashboard/docente/", "/preguntas/", "/preguntas/importar/",
            "/cuestionarios/", "/cuestionarios/crear/", f"/cuestionarios/{cid}/editar/",
            f"/cuestionarios/{cid}/previsualizar/", f"/cuestionarios/{cid}/intentos/",
            "/perfil/", "/ajustes/",
        ])

    def test_paginas_admin(self):
        self._ok(self.admin, ["/dashboard/admin/", "/usuarios/"])

    def test_flujo_estudiante_renderiza_cada_pantalla(self):
        self._ok(self.estudiante, ["/dashboard/estudiante/", "/perfil/"])
        self.client.get(f"/evaluacion/iniciar/{self.cuestionario.id}/")
        intento = Intento.objects.get()
        # Con un intento en curso el panel muestra el botón de reanudar
        self._ok(self.estudiante, ["/dashboard/estudiante/", f"/evaluacion/{intento.id}/"])
        self.client.post(
            f"/evaluacion/{intento.id}/finalizar/",
            {"respuestas_json": json.dumps(respuestas_correctas(self.cuestionario))},
        )
        self._ok(self.estudiante, [f"/evaluacion/{intento.id}/resultado/", "/dashboard/estudiante/"])
        panel = self.client.get("/dashboard/estudiante/").context
        self.assertEqual(panel["promedio_global"], Decimal("5.00"))
        destacado = panel["cuestionario_destacado"]
        self.assertEqual(destacado.intentos_hechos, 1)
        self.assertEqual(destacado.intentos_restantes, 1)
        intento.refresh_from_db()
        self.assertEqual(intento.calificacion, Decimal("5.00"))


class PerfilTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.user = crear_usuario("alumno", "estudiante")

    def test_cambiar_clave_mantiene_la_sesion(self):
        self.client.force_login(self.user)
        nueva = "Nueva-Clave-2026"
        self.client.post("/perfil/cambiar-password/", {"nueva_password": nueva, "confirmar_password": nueva})
        self.assertEqual(self.client.get("/perfil/").status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(nueva))
        self.assertFalse(self.user.check_password(CLAVE))

    def test_logout_cierra_la_sesion(self):
        self.client.force_login(self.user)
        r = self.client.get("/logout/")
        self.assertRedirects(r, "/login/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_clave_corta_se_rechaza(self):
        self.client.force_login(self.user)
        self.client.post("/perfil/cambiar-password/", {"nueva_password": "corta1", "confirmar_password": "corta1"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CLAVE))


class AccesosDemoTests(TestCase):
    def test_ocultos_si_la_opcion_esta_desactivada(self):
        with self.settings(MOSTRAR_ACCESOS_DEMO=False):
            self.assertNotContains(self.client.get("/login/"), "data-demo-usuario")

    def test_visibles_en_desarrollo(self):
        with self.settings(MOSTRAR_ACCESOS_DEMO=True):
            self.assertContains(self.client.get("/login/"), "data-demo-usuario")

    def test_ajustes_es_de_solo_lectura(self):
        sembrar_roles()
        self.client.force_login(crear_usuario("prof", "docente"))
        r = self.client.get("/ajustes/")
        self.assertContains(r, "America/Bogota")
        self.assertNotContains(r, "<form")
        self.assertEqual(self.client.post("/ajustes/guardar/").status_code, 404)
