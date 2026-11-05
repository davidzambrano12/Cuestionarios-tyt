"""Emisión y revocación de los tokens JWT que acompañan a la sesión web."""
from rest_framework_simplejwt.tokens import RefreshToken

DURACION_COOKIE_SEG = 86400


def _claims(user) -> dict:
    perfil = getattr(user, "perfil", None)
    rol = perfil.rol if perfil else None
    if rol:
        rol_codigo, rol_nombre = rol.codigo, rol.nombre
    elif user.is_superuser:
        rol_codigo, rol_nombre = "admin", "Administrador"
    else:
        rol_codigo, rol_nombre = "estudiante", "Estudiante"
    if user.is_superuser:
        permisos = ["*"]
    else:
        permisos = list(rol.permisos.values_list("codigo", flat=True)) if rol else []
    return {"rol_codigo": rol_codigo, "rol_nombre": rol_nombre, "permisos": permisos}


def emitir_tokens(user) -> tuple[str, str]:
    """Retorna (access, refresh) con los claims de rol y permisos."""
    claims = _claims(user)
    refresh = RefreshToken.for_user(user)
    refresh["username"] = user.username
    refresh["email"] = user.email
    refresh["full_name"] = user.get_full_name() or user.username
    for clave, valor in claims.items():
        refresh[clave] = valor

    access = refresh.access_token
    access["username"] = user.username
    for clave, valor in claims.items():
        access[clave] = valor
    return str(access), str(refresh)


def guardar_en_cookies(response, access: str, refresh: str):
    for nombre, valor in (("access_token", access), ("refresh_token", refresh)):
        response.set_cookie(nombre, valor, max_age=DURACION_COOKIE_SEG, httponly=False, samesite="Lax")
    return response


def revocar(refresh_token: str | None) -> None:
    if not refresh_token:
        return
    try:
        RefreshToken(refresh_token).blacklist()
    except Exception:
        # Token inválido o ya revocado: no impide cerrar sesión
        pass


def limpiar_cookies(response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
