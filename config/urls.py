from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from core import views as core_views

urlpatterns = [
    # Portada principal institucional
    path("", core_views.landing_view, name="landing"),

    # Autenticación Web
    path("login/", core_views.login_view, name="login"),
    path("logout/", core_views.logout_view, name="logout"),

    # Django Admin
    path("admin/", admin.site.urls),

    # Módulos Core (Dashboards, Usuarios, Roles, Perfil, JWT)
    path("", include("core.urls")),

    # Módulos Preguntas, Cuestionarios y Evaluación
    path("", include("preguntas.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
