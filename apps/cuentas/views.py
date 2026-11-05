"""Cuentas: autenticación, perfil, ajustes y gestión de usuarios y roles."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import requiere_permiso
from apps.core.models import PerfilUsuario, PermisoSistema, Rol
from . import tokens
from .services import url_panel

LONGITUD_MINIMA_CLAVE = 8
CORREO_SOPORTE = "soporte.sistemas@uniputumayo.edu.co"


def login_view(request):
    """Inicio de sesión por usuario o correo: crea la sesión Django y emite el JWT en cookies."""
    if request.user.is_authenticated:
        return redirect(url_panel(request.user))

    if request.method == "POST":
        identificador = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if "@" in identificador:
            por_correo = User.objects.filter(email__iexact=identificador).first()
            if por_correo:
                identificador = por_correo.username

        user = authenticate(request, username=identificador, password=password)
        if user is None:
            messages.error(request, "Credenciales incorrectas. Verifique su usuario y contraseña.")
        elif not user.is_active:
            messages.error(request, "Su cuenta institucional ha sido desactivada o suspendida.")
        else:
            login(request, user)
            access, refresh = tokens.emitir_tokens(user)
            return tokens.guardar_en_cookies(redirect(url_panel(user)), access, refresh)

    return render(request, "cuentas/login.html", {"accesos_demo": settings.MOSTRAR_ACCESOS_DEMO})


def logout_view(request):
    """Cierra la sesión, revoca el refresh token y limpia las cookies JWT."""
    tokens.revocar(request.COOKIES.get("refresh_token"))
    logout(request)
    return tokens.limpiar_cookies(redirect("login"))


@login_required
@requiere_permiso("roles.gestionar")
def usuarios_roles_view(request):
    """Gestión de usuarios institucionales y roles/permisos configurables."""
    usuarios = User.objects.all().select_related("perfil", "perfil__rol").order_by("-id")
    roles = Rol.objects.all().prefetch_related("permisos").order_by("id")
    todos_permisos = PermisoSistema.objects.all().order_by("modulo", "nombre")

    return render(request, "cuentas/usuarios_roles.html", {
        "usuarios": usuarios,
        "roles": roles,
        "todos_permisos": todos_permisos,
    })


@login_required
@requiere_permiso("usuarios.crear")
def crear_usuario_view(request):
    """Crea un nuevo usuario con perfil institucional y rol."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        rol_id = request.POST.get("rol_id")
        codigo = request.POST.get("codigo_institucional", "").strip() or username

        if User.objects.filter(username=username).exists():
            messages.error(request, f"El nombre de usuario '{username}' ya está en uso.")
            return redirect("cuentas:usuarios_roles")

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            is_active=True,
        )

        rol = Rol.objects.filter(id=rol_id).first()
        PerfilUsuario.objects.create(
            user=user,
            rol=rol,
            codigo_institucional=codigo,
            programa_academico="Ingeniería de Sistemas",
        )

        messages.success(request, f"Usuario '{user.username}' registrado exitosamente.")
    return redirect("cuentas:usuarios_roles")


@login_required
@requiere_permiso("usuarios.editar")
def editar_usuario_view(request, user_id):
    """Actualiza la información institucional y rol de un usuario."""
    user_obj = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        rol_id = request.POST.get("rol_id")
        codigo = request.POST.get("codigo_institucional", "").strip()
        nueva_password = request.POST.get("password", "").strip()

        user_obj.first_name = first_name
        user_obj.last_name = last_name
        user_obj.email = email
        if nueva_password:
            user_obj.set_password(nueva_password)
        user_obj.save()

        perfil, _ = PerfilUsuario.objects.get_or_create(user=user_obj)
        if rol_id:
            perfil.rol = Rol.objects.filter(id=rol_id).first()
        perfil.codigo_institucional = codigo or user_obj.username
        perfil.save()

        messages.success(request, f"Datos del usuario '{user_obj.get_full_name() or user_obj.username}' actualizados exitosamente.")
    return redirect("cuentas:usuarios_roles")


@login_required
@requiere_permiso("usuarios.activar_desactivar")
def toggle_usuario_estado_view(request, user_id):
    """Suspende o reactiva el acceso de un usuario."""
    if request.method == "POST":
        user_obj = get_object_or_404(User, id=user_id)
        if user_obj == request.user:
            messages.error(request, "No puede suspender su propia cuenta de administrador.")
            return redirect("cuentas:usuarios_roles")

        user_obj.is_active = not user_obj.is_active
        user_obj.save()
        estado = "reactivada" if user_obj.is_active else "suspendida"
        messages.success(request, f"Cuenta de '{user_obj.username}' {estado} correctamente.")
    return redirect("cuentas:usuarios_roles")


@login_required
@requiere_permiso("roles.gestionar")
def crear_rol_view(request):
    """Crea un rol configurable con permisos específicos seleccionados."""
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        codigo = request.POST.get("codigo", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        permisos_ids = request.POST.getlist("permisos")

        if Rol.objects.filter(codigo=codigo).exists():
            messages.error(request, f"Ya existe un rol con el código '{codigo}'.")
            return redirect("cuentas:usuarios_roles")

        rol = Rol.objects.create(
            nombre=nombre,
            codigo=codigo,
            descripcion=descripcion,
            activo=True,
            es_sistema=False,
        )
        if permisos_ids:
            rol.permisos.set(permisos_ids)

        messages.success(request, f"Rol personalizado '{rol.nombre}' creado exitosamente.")
    return redirect("cuentas:usuarios_roles")


@login_required
@requiere_permiso("roles.gestionar")
def toggle_rol_estado_view(request, rol_id):
    """Activa o desactiva un rol personalizado."""
    if request.method == "POST":
        rol = get_object_or_404(Rol, id=rol_id)
        if rol.es_sistema:
            messages.error(request, "Los roles del sistema predeterminados no se pueden desactivar.")
            return redirect("cuentas:usuarios_roles")

        rol.activo = not rol.activo
        rol.save()
        estado = "activado" if rol.activo else "desactivado"
        messages.success(request, f"Rol '{rol.nombre}' {estado}.")
    return redirect("cuentas:usuarios_roles")


@login_required
@requiere_permiso("roles.gestionar")
def editar_rol_permisos_view(request, rol_id):
    """Actualiza la lista de permisos asignados a un rol."""
    if request.method == "POST":
        rol = get_object_or_404(Rol, id=rol_id)
        permisos_ids = request.POST.getlist("permisos")
        rol.permisos.set(permisos_ids)
        messages.success(request, f"Permisos actualizados para el rol '{rol.nombre}'.")
    return redirect("cuentas:usuarios_roles")


@login_required
def api_rol_permisos(request, rol_id):
    """Retorna en JSON los IDs de permisos asignados a un rol."""
    rol = get_object_or_404(Rol, id=rol_id)
    ids = list(rol.permisos.values_list("id", flat=True))
    return JsonResponse({"rol_id": rol.id, "nombre": rol.nombre, "permisos_ids": ids})


@login_required
def perfil_view(request):
    """Vista de perfil institucional del usuario actual."""
    return render(request, "cuentas/perfil.html", {"user": request.user})


@login_required
def actualizar_perfil_view(request):
    """Actualiza teléfono e información académica del perfil."""
    if request.method == "POST":
        perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
        perfil.telefono = request.POST.get("telefono", "").strip()
        programa_semestre = request.POST.get("programa", "").strip()
        if "-" in programa_semestre:
            partes = programa_semestre.split("-")
            perfil.programa_academico = partes[0].strip()
            perfil.semestre = partes[1].strip()
        perfil.save()
        messages.success(request, "Datos de perfil actualizados exitosamente.")
    return redirect("cuentas:perfil")


@login_required
def cambiar_password_view(request):
    """Cambia la contraseña del usuario logueado con verificación."""
    if request.method == "POST":
        nueva = request.POST.get("nueva_password", "")
        confirmar = request.POST.get("confirmar_password", "")

        if len(nueva) < LONGITUD_MINIMA_CLAVE:
            messages.error(request, f"La nueva contraseña debe tener al menos {LONGITUD_MINIMA_CLAVE} caracteres.")
            return redirect("cuentas:perfil")
        if nueva != confirmar:
            messages.error(request, "Las contraseñas no coinciden.")
            return redirect("cuentas:perfil")

        request.user.set_password(nueva)
        request.user.save()
        update_session_auth_hash(request, request.user)  # no cerrar la sesión actual
        messages.success(request, "Contraseña actualizada exitosamente.")
    return redirect("cuentas:perfil")


@login_required
def ajustes_view(request):
    """Información de la configuración vigente del sistema (solo lectura)."""
    return render(request, "cuentas/ajustes.html", {
        "zona_horaria": settings.TIME_ZONE,
        "idioma": settings.LANGUAGE_CODE,
        "entorno": "Desarrollo" if settings.DEBUG else "Producción",
        "correo_soporte": CORREO_SOPORTE,
    })
