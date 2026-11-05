"""
Base de las pruebas de navegador (Playwright).

Se ejecutan solo si se pide explícitamente, para que `manage.py test`
siga siendo rápido y no exija Playwright:

    pip install -r requirements-dev.txt
    playwright install chromium          # o usa un navegador instalado (ver E2E_NAVEGADOR)
    E2E=1 python manage.py test pruebas_e2e

Variables de entorno:
    E2E=1             activa estas pruebas.
    E2E_NAVEGADOR     canal de Playwright: chromium (por defecto), msedge o chrome.
    E2E_CAPTURAS      carpeta donde guardar capturas de pantalla (opcional).
"""
import os
import unittest

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client

ACTIVAS = os.environ.get("E2E") == "1"

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Playwright es dependencia solo de desarrollo
    sync_playwright = None

# Playwright usa un bucle de eventos propio; Django lo detectaría como contexto asíncrono
if ACTIVAS:
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@unittest.skipUnless(ACTIVAS, "Pruebas de navegador desactivadas: usa E2E=1")
@unittest.skipIf(sync_playwright is None, "Playwright no está instalado (requirements-dev.txt)")
class PruebaNavegador(StaticLiveServerTestCase):
    host = "localhost"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        canal = os.environ.get("E2E_NAVEGADOR", "chromium")
        opciones = {"headless": True}
        if canal != "chromium":
            opciones["channel"] = canal
        cls.navegador = cls.playwright.chromium.launch(**opciones)

    @classmethod
    def tearDownClass(cls):
        cls.navegador.close()
        cls.playwright.stop()
        super().tearDownClass()

    def abrir(self, ruta, usuario=None, ancho=1366, alto=900, aceptar_dialogos=True):
        """Abre `ruta` (con sesión de `usuario` si se indica). Retorna (página, errores JS)."""
        contexto = self.navegador.new_context(viewport={"width": ancho, "height": alto})
        if usuario is not None:
            cliente = Client()
            cliente.force_login(usuario)
            contexto.add_cookies([{
                "name": settings.SESSION_COOKIE_NAME,
                "value": cliente.cookies[settings.SESSION_COOKIE_NAME].value,
                "domain": "localhost",
                "path": "/",
            }])
        pagina = contexto.new_page()
        errores = []
        pagina.on("pageerror", lambda error: errores.append(str(error)))
        self.dialogos = []
        if aceptar_dialogos:
            pagina.on("dialog", lambda d: (self.dialogos.append(d.message), d.accept()))
        else:
            pagina.on("dialog", lambda d: (self.dialogos.append(d.message), d.dismiss()))
        pagina.goto(self.live_server_url + ruta)
        return pagina, errores

    def capturar(self, pagina, nombre):
        carpeta = os.environ.get("E2E_CAPTURAS")
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
            pagina.screenshot(path=os.path.join(carpeta, f"{nombre}.png"), full_page=True)

    @staticmethod
    def modal_abierto(pagina, id_modal):
        return pagina.evaluate(f"document.getElementById('{id_modal}').classList.contains('open')")
