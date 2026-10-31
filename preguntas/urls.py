from django.urls import path
from . import views

app_name = "preguntas"

urlpatterns = [
    # Banco de Preguntas
    path("preguntas/", views.banco_preguntas, name="banco"),
    path("preguntas/crear/", views.crear_pregunta, name="crear"),
    path("preguntas/<int:pregunta_id>/editar/", views.editar_pregunta, name="editar"),
    path("preguntas/<int:pregunta_id>/toggle-estado/", views.toggle_pregunta_estado, name="toggle_estado"),

    # Importador Excel
    path("preguntas/importar/", views.importar_preguntas, name="importar"),
    path("preguntas/importar/previsualizar/", views.previsualizar_importacion, name="previsualizar"),
    path("preguntas/importar/corregir/", views.corregir_fila_importacion, name="corregir_fila"),
    path("preguntas/importar/confirmar/", views.confirmar_importacion, name="confirmar"),
    path("preguntas/importar/cancelar/", views.cancelar_importacion, name="cancelar"),

    # Cuestionarios
    path("cuestionarios/", views.cuestionarios_list, name="cuestionarios_list"),
    path("cuestionarios/crear/", views.configurar_cuestionario, name="cuestionario_crear"),
    path("cuestionarios/<int:cuestionario_id>/editar/", views.configurar_cuestionario, name="cuestionario_editar"),
    path("cuestionarios/<int:cuestionario_id>/previsualizar/", views.previsualizar_cuestionario, name="cuestionario_previsualizar"),


    # Evaluación en Vivo y Calificación
    path("evaluacion/iniciar/<int:cuestionario_id>/", views.iniciar_evaluacion, name="iniciar_evaluacion"),
    path("evaluacion/<int:intento_id>/", views.evaluacion_en_vivo, name="evaluacion_en_vivo"),
    path("evaluacion/<int:intento_id>/finalizar/", views.finalizar_evaluacion, name="finalizar_evaluacion"),
    path("evaluacion/<int:intento_id>/resultado/", views.resultado_evaluacion, name="resultado_evaluacion"),
]
