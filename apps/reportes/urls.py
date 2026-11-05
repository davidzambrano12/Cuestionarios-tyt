from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("dashboard/admin/", views.panel_admin, name="panel_admin"),
    path("dashboard/docente/", views.panel_docente, name="panel_docente"),
    path("cuestionarios/<int:cuestionario_id>/intentos/", views.cuestionario_intentos, name="intentos"),
    path("cuestionarios/<int:cuestionario_id>/intentos/exportar/", views.exportar_intentos_excel, name="exportar_excel"),
    path(
        "cuestionarios/<int:cuestionario_id>/intentos/reiniciar-estudiante/<str:codigo_estudiante>/",
        views.reiniciar_estudiante_cuestionario,
        name="reiniciar_estudiante",
    ),
    path("cuestionarios/intentos/<int:intento_id>/reiniciar/", views.reiniciar_intento, name="reiniciar_intento"),
]
