"""Configuración de producción: todo lo sensible es obligatorio desde el entorno."""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403


def _requerida(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise ImproperlyConfigured(f"Falta la variable de entorno obligatoria {nombre}.")
    return valor


def _lista(valor: str) -> list[str]:
    return [item.strip() for item in valor.split(",") if item.strip()]


DEBUG = False
SECRET_KEY = _requerida("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = _lista(_requerida("DJANGO_ALLOWED_HOSTS"))

# Vercel publica cada despliegue en un dominio propio (VERCEL_URL); se admite también
_vercel = os.environ.get("VERCEL_URL")
if _vercel and _vercel not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_vercel)

# Orígenes HTTPS desde los que se aceptan formularios (login, examen, Swagger).
# Si no se definen, se derivan de ALLOWED_HOSTS.
CSRF_TRUSTED_ORIGINS = _lista(os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "")) or [
    f"https://*{host}" if host.startswith(".") else f"https://{host}"
    for host in ALLOWED_HOSTS if host != "*"
]

# Vercel termina HTTPS en su proxy y avisa el esquema original con este encabezado
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = True
# HSTS corto (1 hora) mientras se valida el despliegue; se puede ampliar después
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "3600"))

# Subdominios y lista de precarga: el dominio *.vercel.app no es nuestro y ya está precargado
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]

# La aplicación no envía correos hoy; si llegara a hacerlo, usa SMTP de producción
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.smtp.EmailBackend"}}

# Errores visibles en los registros de Vercel (con DEBUG=False no se muestran en la página)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"consola": {"class": "logging.StreamHandler"}},
    "loggers": {"django": {"handlers": ["consola"], "level": "WARNING"}},
}
