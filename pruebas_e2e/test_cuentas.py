"""Inicio y cierre de sesión, usuarios y roles, y ajustes del sistema."""
from django.contrib.auth.models import User

from apps.core.models import ConfiguracionSistema, Rol
from apps.core.tests.factories import CLAVE, crear_usuario, sembrar_roles

from .base import PruebaNavegador


class CuentasTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.admin = crear_usuario("jefe", "admin", is_superuser=True, is_staff=True)
        self.docente = crear_usuario("prof", "docente")

    def test_login_y_logout(self):
        pg, errores = self.abrir("/login/")
        pg.fill("#username", "prof")
        pg.fill("#password", "mala")
        pg.click('[data-ref="enviar"]')
        pg.wait_for_selector("#login-error:not([hidden])")
        self.assertIn("incorrectos", pg.inner_text("#login-error"))
        pg.click('[data-accion="ver-clave"]')
        self.assertEqual(pg.get_attribute("#password", "type"), "text")

        pg.fill("#password", CLAVE)
        pg.click('[data-ref="enviar"]')
        pg.wait_for_url("**/dashboard/docente/")
        self.assertIsNotNone(pg.evaluate("localStorage.getItem('access_token')"))

        # Cuenta: un solo acceso, en la barra superior (la barra lateral ya no lo repite)
        self.assertEqual(pg.locator(".sidebar a[href='/perfil/']").count(), 0)
        boton = ".menu-cuenta__boton"
        self.assertIn("Docente", pg.inner_text(boton))
        self.assertFalse(pg.is_visible("#menu-cuenta-lista"))
        pg.focus(boton)
        pg.keyboard.press("Enter")
        self.assertEqual(pg.get_attribute(boton, "aria-expanded"), "true")
        self.assertEqual(pg.evaluate("document.activeElement.textContent.trim()"), "Mi perfil")
        pg.keyboard.press("ArrowDown")
        self.assertEqual(pg.evaluate("document.activeElement.textContent.trim()"), "Cerrar sesión")
        pg.keyboard.press("Escape")
        self.assertFalse(pg.is_visible("#menu-cuenta-lista"))
        self.assertEqual(pg.evaluate("document.activeElement.classList.contains('menu-cuenta__boton')"), True)
        pg.click(boton)
        pg.click(".navbar-brand-title")  # clic fuera cierra
        self.assertFalse(pg.is_visible("#menu-cuenta-lista"))

        pg.click(boton)
        self.capturar(pg, "menu_cuenta")
        pg.click("#menu-cuenta-lista [data-cerrar-sesion]")
        pg.wait_for_url("**/login/")
        self.assertIsNone(pg.evaluate("localStorage.getItem('access_token')"))
        self.assertEqual(errores, [])

    def test_usuarios_y_roles(self):
        raro = crear_usuario("dora", "estudiante", first_name="D'Artagnan", last_name='<img src=x onerror="window.__x=1">')
        crear_usuario("suspendido", "docente", is_active=False)
        pg, errores = self.abrir("/usuarios/", self.admin)
        visibles = lambda: pg.locator("#panel-usuarios .tarjeta-cuenta:visible").count()
        total = visibles()

        pg.click('[data-filtro-rol="docente"]')
        pg.click('[data-filtro-estado="inactivo"]')
        self.assertEqual(visibles(), 1)  # filtros combinados
        pg.fill("#filtro-texto", "zzz")
        self.assertTrue(pg.is_visible("#sin-resultados"))
        pg.click('[data-accion="limpiar-filtros"]')
        self.assertEqual(visibles(), total)

        # Nombre con apóstrofo y HTML: antes rompía el botón Editar
        pg.click(f'[data-editar-usuario="{raro.id}"]')
        self.assertEqual(pg.input_value("#eu-nombre"), "D'Artagnan")
        self.assertIsNone(pg.evaluate("window.__x"))
        pg.fill("#eu-nombre", "Dora")
        pg.click('#form-editar-usuario button[type="submit"]')
        pg.wait_for_load_state("networkidle")
        raro.refresh_from_db()
        self.assertEqual(raro.first_name, "Dora")

        pg.click(f'.tarjeta-cuenta:has([data-editar-usuario="{raro.id}"]) button:has-text("Suspender")')
        pg.wait_for_load_state("networkidle")
        self.assertFalse(User.objects.get(id=raro.id).is_active)

        pg.click('[data-pestana="roles"]')
        pg.fill("#filtro-texto", "docente")
        self.assertEqual(pg.locator("#panel-roles .tarjeta-cuenta:visible").count(), 1)
        rol = Rol.objects.get(codigo="docente")
        pg.click(f'[data-editar-permisos="{rol.id}"]')
        pg.wait_for_function("document.getElementById('modal-editar-permisos').classList.contains('open')")
        self.assertEqual(pg.locator("#form-editar-permisos input:checked").count(), rol.permisos.count())
        self.capturar(pg, "usuarios_roles")
        self.assertEqual(errores, [])

    def test_ajustes(self):
        pg, errores = self.abrir("/ajustes/", self.admin)
        pg.fill("#id_correo_soporte", "ayuda@uniputumayo.edu.co")
        pg.click('button[type="submit"]')
        pg.wait_for_load_state("networkidle")
        self.assertEqual(ConfiguracionSistema.actual().correo_soporte, "ayuda@uniputumayo.edu.co")
        pg.goto(self.live_server_url + "/")
        self.assertIn("ayuda@uniputumayo.edu.co", pg.inner_text(".portada-pie"))

        pg, _ = self.abrir("/ajustes/", self.docente)
        self.assertTrue(pg.is_disabled("#id_correo_soporte"))
        self.assertEqual(pg.locator('button[type="submit"]').count(), 0)
        self.assertEqual(errores, [])
