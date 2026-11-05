from django.urls import path

from . import views

app_name = "importaciones"

urlpatterns = [
    path("preguntas/importar/", views.importar_preguntas, name="importar"),
    path("preguntas/importar/previsualizar/", views.previsualizar_importacion, name="previsualizar"),
    path("preguntas/importar/corregir/", views.corregir_fila_importacion, name="corregir_fila"),
    path("preguntas/importar/confirmar/", views.confirmar_importacion, name="confirmar"),
    path("preguntas/importar/cancelar/", views.cancelar_importacion, name="cancelar"),
]
