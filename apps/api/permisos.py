"""
Permisos de la API: reutilizan los mismos códigos de rol que las vistas web
(`apps.core.services.acceso`), así una regla vale igual en la pantalla y en la API.
"""
from rest_framework.permissions import BasePermission

from apps.core.services.acceso import es_personal_docente, tiene_permiso


def requiere(codigo: str) -> type[BasePermission]:
    """Clase de permiso que exige el permiso de rol `codigo` (p. ej. "preguntas.gestionar")."""

    class TienePermiso(BasePermission):
        message = f"Su rol no posee el permiso '{codigo}' requerido para esta acción."

        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and user.is_active and tiene_permiso(user, codigo))

    TienePermiso.__name__ = f"TienePermiso_{codigo.replace('.', '_')}"
    return TienePermiso


class EsEstudiante(BasePermission):
    """Docentes y administradores previsualizan los simulacros; no registran intentos."""
    message = "Solo los estudiantes registran intentos; docentes y administradores previsualizan el simulacro."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active
            and not es_personal_docente(user)
            and tiene_permiso(user, "evaluaciones.responder")
        )
