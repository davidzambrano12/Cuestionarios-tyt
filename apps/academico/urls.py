from django.urls import path

from . import views

app_name = "academico"

urlpatterns = [
    path("cursos/", views.listado, name="listado"),
    path("cursos/nuevo/", views.crear_curso, name="crear"),
    path("cursos/periodos/nuevo/", views.crear_periodo, name="crear_periodo"),
    path("cursos/<int:curso_id>/", views.detalle, name="detalle"),
    path("cursos/<int:curso_id>/editar/", views.editar_curso, name="editar"),
    path("cursos/<int:curso_id>/matricular/", views.matricular, name="matricular"),
    path("cursos/<int:curso_id>/buscar-estudiantes/", views.buscar_estudiantes, name="buscar_estudiantes"),
    path("cursos/<int:curso_id>/revisar-codigos/", views.revisar_codigos, name="revisar_codigos"),
    path("cursos/<int:curso_id>/retirar/<int:matricula_id>/", views.retirar, name="retirar"),
]
