from django.urls import path

from . import views

app_name = "preguntas"

urlpatterns = [
    path("importar/", views.importar_preguntas, name="importar"),
    path("importar/confirmar/", views.confirmar_importacion, name="confirmar"),
    path("importar/cancelar/", views.cancelar_importacion, name="cancelar"),
]
