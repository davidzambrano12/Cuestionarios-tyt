"""Configuración de producción: todo lo sensible es obligatorio desde el entorno."""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403


def _requerida(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise ImproperlyConfigured(f"Falta la variable de entorno obligatoria {nombre}.")
    return valor


DEBUG = False
SECRET_KEY = _requerida("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = _requerida("DJANGO_ALLOWED_HOSTS").split(",")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
