from django.urls import path

from . import views

app_name = "evaluaciones"

urlpatterns = [
    path("dashboard/estudiante/", views.panel_estudiante, name="panel_estudiante"),
    path("evaluacion/iniciar/<int:cuestionario_id>/", views.iniciar_evaluacion, name="iniciar"),
    path("evaluacion/<int:intento_id>/", views.evaluacion_en_vivo, name="sala"),
    path("evaluacion/<int:intento_id>/guardar-respuesta/", views.guardar_respuesta_ajax, name="guardar_respuesta"),
    path("evaluacion/<int:intento_id>/finalizar/", views.finalizar_evaluacion, name="finalizar"),
    path("evaluacion/<int:intento_id>/resultado/", views.resultado_evaluacion, name="resultado"),
]
