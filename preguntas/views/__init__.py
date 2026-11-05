"""
Vistas del módulo de preguntas, cuestionarios y evaluaciones, separadas por
responsabilidad. Cada vista solo traduce la petición HTTP: la lógica de
negocio vive en `preguntas/services/`.
"""
from .banco import banco_preguntas, crear_pregunta, editar_pregunta, toggle_pregunta_estado
from .cuestionarios import configurar_cuestionario, cuestionarios_list, previsualizar_cuestionario
from .evaluacion import (
    evaluacion_en_vivo,
    finalizar_evaluacion,
    guardar_respuesta_ajax,
    iniciar_evaluacion,
    resultado_evaluacion,
)
from .importacion import (
    cancelar_importacion,
    confirmar_importacion,
    corregir_fila_importacion,
    importar_preguntas,
    previsualizar_importacion,
)
from .reportes import (
    cuestionario_intentos,
    exportar_intentos_excel,
    reiniciar_estudiante_cuestionario,
    reiniciar_intento,
)
