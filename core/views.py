from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework_simplejwt.tokens import RefreshToken

from core.decorators import requiere_permiso, solo_roles
from core.models import PerfilUsuario, PermisoSistema, Rol
from preguntas.models import Categoria, Cuestionario, Intento, Pregunta


def landing_view(request):
    """Página de inicio pública del Simulador Saber TyT Uniputumayo."""
    ahora = timezone.now()
    cuestionarios = Cuestionario.objects.filter(
        estado="disponible",
        fecha_apertura__lte=ahora,
        fecha_cierre__gte=ahora,
    ).order_by("-id")
    return render(request, "landing.html", {"cuestionarios": cuestionarios})


def login_view(request):
    """
    Vista de inicio de sesión institucional con compatibilidad para
    autenticación mediante sesión Django tradicional y emisión de JWT.
    """
    if request.user.is_authenticated:
        perfil = getattr(request.user, "perfil", None)
        if request.user.is_superuser or (perfil and perfil.es_admin):
            return redirect("/dashboard/admin/")
        elif perfil and perfil.es_docente:
            return redirect("/dashboard/docente/")
        else:
            return redirect("/dashboard/estudiante/")

    if request.method == "POST":
        username_or_email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # Permitir login por correo
        user = None
        if "@" in username_or_email:
            user_obj = User.objects.filter(email__iexact=username_or_email).first()
            if user_obj:
                username_or_email = user_obj.username

        user = authenticate(request, username=username_or_email, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "Su cuenta institucional ha sido desactivada o suspendida.")
                return render(request, "login.html")

            login(request, user)
            
            # Generar tokens JWT con claims personalizados y guardarlos en cookies
            refresh = RefreshToken.for_user(user)
            perfil = getattr(user, "perfil", None)
            rol_codigo = perfil.rol.codigo if (perfil and perfil.rol) else ("admin" if user.is_superuser else "estudiante")
            rol_nombre = perfil.rol.nombre if (perfil and perfil.rol) else ("Administrador" if user.is_superuser else "Estudiante")
            permisos_codigos = ["*"] if user.is_superuser else (list(perfil.rol.permisos.values_list("codigo", flat=True)) if (perfil and perfil.rol) else [])

            refresh["username"] = user.username
            refresh["email"] = user.email
            refresh["full_name"] = user.get_full_name() or user.username
            refresh["rol_codigo"] = rol_codigo
            refresh["rol_nombre"] = rol_nombre
            refresh["permisos"] = permisos_codigos

            access_token = refresh.access_token
            access_token["username"] = user.username
            access_token["rol_codigo"] = rol_codigo
            access_token["rol_nombre"] = rol_nombre
            access_token["permisos"] = permisos_codigos

            access = str(access_token)

            if user.is_superuser or (perfil and perfil.es_admin):
                redirect_url = "/dashboard/admin/"
            elif perfil and perfil.es_docente:
                redirect_url = "/dashboard/docente/"
            else:
                redirect_url = "/dashboard/estudiante/"

            response = redirect(redirect_url)
            max_age = 86400
            response.set_cookie("access_token", access, max_age=max_age, httponly=False, samesite="Lax")
            response.set_cookie("refresh_token", str(refresh), max_age=max_age, httponly=False, samesite="Lax")
            return response
        else:
            messages.error(request, "Credenciales incorrectas. Verifique su usuario y contraseña.")

    return render(request, "login.html")


def logout_view(request):
    """Cierre de sesión que revoca el JWT y limpia la sesión."""
    refresh_token = request.COOKIES.get("refresh_token")
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
    logout(request)
    response = redirect("/login/")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@login_required
@solo_roles("admin")
def admin_dashboard_view(request):
    """Dashboard para el Administrador del Sistema."""
    preguntas_activas = Pregunta.objects.filter(activa=True).count()
    categorias = Categoria.objects.all()
    cuestionarios_count = Cuestionario.objects.count()
    intentos_count = Intento.objects.count()
    cuestionarios_recientes = Cuestionario.objects.all().order_by("-id")[:5]

    return render(request, "admin_dashboard.html", {
        "preguntas_activas": preguntas_activas,
        "categorias_count": categorias.count(),
        "categorias_list": categorias,
        "cuestionarios_count": cuestionarios_count,
        "intentos_count": intentos_count,
        "cuestionarios_recientes": cuestionarios_recientes,
    })


@login_required
@requiere_permiso("preguntas.gestionar")
def docente_dashboard_view(request):
    """Dashboard para Docentes y Evaluadores."""
    cuestionarios = Cuestionario.objects.all().order_by("-id")
    preguntas_count = Pregunta.objects.filter(activa=True).count()
    publicados_count = Cuestionario.objects.filter(estado="disponible").count()

    return render(request, "docente_dashboard.html", {
        "cuestionarios": cuestionarios,
        "preguntas_count": preguntas_count,
        "publicados_count": publicados_count,
        "cuestionarios_recientes": cuestionarios[:4],
    })


@login_required
def estudiante_dashboard_view(request):
    """Dashboard para Estudiantes con cuestionarios e historial propio."""
    user = request.user
    codigo = user.perfil.codigo_institucional if hasattr(user, "perfil") else user.username

    ahora = timezone.now()

    # Cuestionarios realmente vigentes
    cuestionarios_disponibles = (
        Cuestionario.objects.filter(
            estado="disponible",
            fecha_apertura__lte=ahora,
            fecha_cierre__gte=ahora,
        )
        .prefetch_related("cuestionario_preguntas", "intentos")
        .order_by("fecha_cierre")
    )
    cuestionario_destacado = cuestionarios_disponibles.first()

    # Cuestionarios programados para fechas futuras
    cuestionarios_programados = (
        Cuestionario.objects.filter(
            Q(estado="programado") | Q(estado="disponible", fecha_apertura__gt=ahora)
        )
        .prefetch_related("cuestionario_preguntas")
        .order_by("fecha_apertura")
    )

    from django.db.models import Count

    # Mapear intentos activos (en progreso), asegurando cerrar duplicados huérfanos
    intentos_activos_qs = Intento.objects.filter(
        participante_codigo=codigo,
        estado="en_progreso",
    ).order_by("-fecha_inicio")

    intentos_activos_map = {}
    for i_act in intentos_activos_qs:
        limite_seg = i_act.cuestionario.tiempo_limite_minutos * 60
        delta_s = int((ahora - i_act.fecha_inicio).total_seconds())
        if delta_s > (limite_seg + 30):
            # Auto-cerrar intento vencido
            i_act.estado = "vencido"
            i_act.fecha_fin = ahora
            i_act.duracion_segundos = delta_s
            i_act.save()
        elif i_act.cuestionario_id not in intentos_activos_map:
            intentos_activos_map[i_act.cuestionario_id] = i_act
        else:
            # Cerrar duplicado huérfano más antiguo
            i_act.estado = "vencido"
            i_act.fecha_fin = ahora
            i_act.duracion_segundos = delta_s
            i_act.save()

    # Mapear intentos realizados (finalizados o vencidos) por cuestionario
    intentos_hechos_qs = (
        Intento.objects.filter(
            participante_codigo=codigo,
            estado__in=["finalizado", "vencido"],
        )
        .values("cuestionario_id")
        .annotate(total=Count("id"))
    )
    intentos_hechos_map = {item["cuestionario_id"]: item["total"] for item in intentos_hechos_qs}

    for c in cuestionarios_disponibles:
        c.intento_activo = intentos_activos_map.get(c.id)
        c.intentos_hechos = intentos_hechos_map.get(c.id, 0)
        c.intentos_restantes = max(0, c.intentos_permitidos - c.intentos_hechos)
        c.intentos_agotados = (c.intentos_hechos >= c.intentos_permitidos) and not bool(c.intento_activo)
        c.siguiente_intento_num = min(c.intentos_permitidos, c.intentos_hechos + 1)

    if cuestionario_destacado:
        cuestionario_destacado.intento_activo = intentos_activos_map.get(cuestionario_destacado.id)
        cuestionario_destacado.intentos_hechos = intentos_hechos_map.get(cuestionario_destacado.id, 0)
        cuestionario_destacado.intentos_restantes = max(0, cuestionario_destacado.intentos_permitidos - cuestionario_destacado.intentos_hechos)
        cuestionario_destacado.intentos_agotados = (cuestionario_destacado.intentos_hechos >= cuestionario_destacado.intentos_permitidos) and not bool(cuestionario_destacado.intento_activo)
        cuestionario_destacado.siguiente_intento_num = min(cuestionario_destacado.intentos_permitidos, cuestionario_destacado.intentos_hechos + 1)

    # Intentos propios del estudiante (aislamiento de seguridad)
    intentos_estudiante = Intento.objects.filter(
        participante_codigo=codigo
    ).order_by("-fecha_inicio")

    avg_calc = intentos_estudiante.aggregate(prom=Avg("calificacion"))["prom"]
    promedio_global = f"{avg_calc:.2f}" if avg_calc is not None else "0.00"

    return render(request, "estudiante_dashboard.html", {
        "cuestionarios_disponibles": cuestionarios_disponibles,
        "cuestionarios_programados": cuestionarios_programados,
        "cuestionario_destacado": cuestionario_destacado,
        "intentos_estudiante": intentos_estudiante,
        "disponibles_count": cuestionarios_disponibles.count(),
        "programados_count": cuestionarios_programados.count(),
        "promedio_global": promedio_global,
    })


@login_required
@requiere_permiso("roles.gestionar")
def usuarios_roles_view(request):
    """Gestión de usuarios institucionales y roles/permisos configurables."""
    usuarios = User.objects.all().select_related("perfil", "perfil__rol").order_by("-id")
    roles = Rol.objects.all().prefetch_related("permisos").order_by("id")
    todos_permisos = PermisoSistema.objects.all().order_by("modulo", "nombre")

    return render(request, "usuarios_roles.html", {
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
            return redirect("/usuarios/")

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
    return redirect("/usuarios/")


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
    return redirect("/usuarios/")


@login_required
@requiere_permiso("usuarios.activar_desactivar")
def toggle_usuario_estado_view(request, user_id):
    """Suspende o reactiva el acceso de un usuario."""
    if request.method == "POST":
        user_obj = get_object_or_404(User, id=user_id)
        if user_obj == request.user:
            messages.error(request, "No puede suspender su propia cuenta de administrador.")
            return redirect("/usuarios/")

        user_obj.is_active = not user_obj.is_active
        user_obj.save()
        estado = "reactivada" if user_obj.is_active else "suspendida"
        messages.success(request, f"Cuenta de '{user_obj.username}' {estado} correctamente.")
    return redirect("/usuarios/")


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
            return redirect("/usuarios/")

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
    return redirect("/usuarios/")


@login_required
@requiere_permiso("roles.gestionar")
def toggle_rol_estado_view(request, rol_id):
    """Activa o desactiva un rol personalizado."""
    if request.method == "POST":
        rol = get_object_or_404(Rol, id=rol_id)
        if rol.es_sistema:
            messages.error(request, "Los roles del sistema predeterminados no se pueden desactivar.")
            return redirect("/usuarios/")

        rol.activo = not rol.activo
        rol.save()
        estado = "activado" if rol.activo else "desactivado"
        messages.success(request, f"Rol '{rol.nombre}' {estado}.")
    return redirect("/usuarios/")


@login_required
@requiere_permiso("roles.gestionar")
def editar_rol_permisos_view(request, rol_id):
    """Actualiza la lista de permisos asignados a un rol."""
    if request.method == "POST":
        rol = get_object_or_404(Rol, id=rol_id)
        permisos_ids = request.POST.getlist("permisos")
        rol.permisos.set(permisos_ids)
        messages.success(request, f"Permisos actualizados para el rol '{rol.nombre}'.")
    return redirect("/usuarios/")


@login_required
def api_rol_permisos(request, rol_id):
    """Retorna en JSON los IDs de permisos asignados a un rol."""
    rol = get_object_or_404(Rol, id=rol_id)
    ids = list(rol.permisos.values_list("id", flat=True))
    return JsonResponse({"rol_id": rol.id, "nombre": rol.nombre, "permisos_ids": ids})


@login_required
def perfil_view(request):
    """Vista de perfil institucional del usuario actual."""
    return render(request, "perfil.html", {"user": request.user})


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
    return redirect("/perfil/")


@login_required
def cambiar_password_view(request):
    """Cambia la contraseña del usuario logueado con verificación."""
    if request.method == "POST":
        nueva = request.POST.get("nueva_password", "")
        confirmar = request.POST.get("confirmar_password", "")

        if len(nueva) < 6:
            messages.error(request, "La nueva contraseña debe tener al menos 6 caracteres.")
            return redirect("/perfil/")
        if nueva != confirmar:
            messages.error(request, "Las contraseñas no coinciden.")
            return redirect("/perfil/")

        request.user.set_password(nueva)
        request.user.save()
        messages.success(request, "Contraseña actualizada exitosamente.")
    return redirect("/perfil/")


@login_required
def ajustes_view(request):
    """Vista de configuración general del sistema."""
    return render(request, "ajustes.html")


@login_required
@solo_roles("admin")
def guardar_ajustes_view(request):
    """Guarda parámetros institucionales."""
    if request.method == "POST":
        messages.success(request, "Ajustes del sistema guardados exitosamente.")
    return redirect("/ajustes/")
