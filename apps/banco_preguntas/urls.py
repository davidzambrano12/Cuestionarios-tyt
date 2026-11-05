from django.urls import path

from . import views

app_name = "banco_preguntas"

urlpatterns = [
    path("preguntas/", views.banco_preguntas, name="banco"),
    path("preguntas/crear/", views.crear_pregunta, name="crear"),
    path("preguntas/<int:pregunta_id>/editar/", views.editar_pregunta, name="editar"),
    path("preguntas/<int:pregunta_id>/toggle-estado/", views.toggle_pregunta_estado, name="toggle_estado"),
]
