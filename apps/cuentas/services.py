"""Navegación posterior al inicio de sesión."""
from django.urls import reverse

from apps.core.services.acceso import perfil_de


def url_panel(user) -> str:
    """Panel de inicio que corresponde al rol del usuario."""
    perfil = perfil_de(user)
    if user.is_superuser or (perfil and perfil.es_admin):
        return reverse("reportes:panel_admin")
    if perfil and perfil.es_docente:
        return reverse("reportes:panel_docente")
    return reverse("evaluaciones:panel_estudiante")
