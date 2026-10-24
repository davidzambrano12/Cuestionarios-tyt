from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from .jwt_auth import CustomTokenObtainPairView, LogoutView, UserProfileMeView

app_name = "core"

urlpatterns = [
    # Dashboards por rol
    path("dashboard/admin/", views.admin_dashboard_view, name="admin_dashboard"),
    path("dashboard/docente/", views.docente_dashboard_view, name="docente_dashboard"),
    path("dashboard/estudiante/", views.estudiante_dashboard_view, name="estudiante_dashboard"),

    # Gestión de Usuarios
    path("usuarios/", views.usuarios_roles_view, name="usuarios_roles"),
    path("usuarios/crear/", views.crear_usuario_view, name="crear_usuario"),
    path("usuarios/<int:user_id>/editar/", views.editar_usuario_view, name="editar_usuario"),
    path("usuarios/<int:user_id>/toggle-estado/", views.toggle_usuario_estado_view, name="toggle_usuario_estado"),

    # Gestión de Roles y Permisos configurables
    path("roles/crear/", views.crear_rol_view, name="crear_rol"),
    path("roles/<int:rol_id>/toggle-estado/", views.toggle_rol_estado_view, name="toggle_rol_estado"),
    path("roles/<int:rol_id>/editar-permisos/", views.editar_rol_permisos_view, name="editar_rol_permisos"),
    path("api/roles/<int:rol_id>/permisos/", views.api_rol_permisos, name="api_rol_permisos"),

    # Perfil y Ajustes
    path("perfil/", views.perfil_view, name="perfil"),
    path("perfil/actualizar/", views.actualizar_perfil_view, name="actualizar_perfil"),
    path("perfil/cambiar-password/", views.cambiar_password_view, name="cambiar_password"),
    path("ajustes/", views.ajustes_view, name="ajustes"),
    path("ajustes/guardar/", views.guardar_ajustes_view, name="guardar_ajustes"),

    # API JWT Endpoints
    path("api/auth/token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="jwt_logout"),
    path("api/auth/me/", UserProfileMeView.as_view(), name="user_me"),
]
