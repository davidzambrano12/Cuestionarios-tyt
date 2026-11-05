from django.urls import path

from . import views

app_name = "cuestionarios"

urlpatterns = [
    path("cuestionarios/", views.cuestionarios_list, name="listado"),
    path("cuestionarios/crear/", views.configurar_cuestionario, name="crear"),
    path("cuestionarios/<int:cuestionario_id>/editar/", views.configurar_cuestionario, name="editar"),
    path("cuestionarios/<int:cuestionario_id>/previsualizar/", views.previsualizar_cuestionario, name="previsualizar"),
]
