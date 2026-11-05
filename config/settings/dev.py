"""Configuración de desarrollo local."""
import os

from .base import *  # noqa: F401,F403

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

# Solo para desarrollo: en producción la clave es obligatoria (ver prod.py)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-solo-para-desarrollo-local")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
