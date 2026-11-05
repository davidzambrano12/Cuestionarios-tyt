from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.cuentas import views as cuentas_views
from apps.cuestionarios import views as cuestionarios_views

urlpatterns = [
    path("", cuestionarios_views.landing, name="landing"),
    path("login/", cuentas_views.login_view, name="login"),
    path("logout/", cuentas_views.logout_view, name="logout"),
    path("admin/", admin.site.urls),

    path("", include("apps.cuentas.urls")),
    path("", include("apps.banco_preguntas.urls")),
    path("", include("apps.importaciones.urls")),
    path("", include("apps.cuestionarios.urls")),
    path("", include("apps.evaluaciones.urls")),
    path("", include("apps.reportes.urls")),
    path("", include("apps.academico.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
