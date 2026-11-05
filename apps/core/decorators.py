from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect


def requiere_permiso(codigo_permiso: str):
    """
    Decorador para vistas de Django que restringe el acceso según
    los permisos del usuario en la base de datos (seguridad verificada en el servidor).
    """
    def decorador(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({"detail": "Autenticación requerida."}, status=401)
                messages.warning(request, "Debe iniciar sesión para acceder a este recurso.")
                return redirect_to_login(request.get_full_path())

            if not request.user.is_active:
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({"detail": "Su cuenta está desactivada o suspendida."}, status=403)
                messages.error(request, "Su cuenta institucional ha sido suspendida. Contacte al administrador.")
                return redirect("login")

            # Superusuarios de Django tienen acceso total
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Verificar a través del perfil y rol configurado
            perfil = getattr(request.user, "perfil", None)
            if perfil and perfil.tiene_permiso(codigo_permiso):
                return view_func(request, *args, **kwargs)

            # Rechazar acceso en el servidor si no tiene el permiso
            if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                return JsonResponse({
                    "error": "Acceso Denegado",
                    "detail": f"Su rol no posee el permiso '{codigo_permiso}' requerido para esta acción."
                }, status=403)

            return HttpResponseForbidden(f"""
                <div style="font-family:Roboto, 'Segoe UI', sans-serif; color:#231F20; text-align:center; padding:50px;">
                    <h1 style="color:#A21F1F;">403 - Acceso Denegado</h1>
                    <p>Su rol actual no cuenta con el permiso <code>{codigo_permiso}</code> para realizar esta acción.</p>
                    <p>Esta restricción está validada directamente en el servidor Django.</p>
                    <a href="javascript:history.back()" style="display:inline-block; margin-top:20px; padding:10px 20px; background:#18668F; color:#fff; text-decoration:none; border-radius:6px;">Volver</a>
                </div>
            """)
        return _wrapped_view
    return decorador


def solo_roles(*codigos_roles):
    """
    Decorador para restringir una vista a uno o más códigos de rol específicos.
    """
    def decorador(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            perfil = getattr(request.user, "perfil", None)
            if perfil and perfil.rol and perfil.rol.activo and (perfil.rol.codigo in codigos_roles):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("No tiene el rol necesario para acceder a esta vista.")
        return _wrapped_view
    return decorador
