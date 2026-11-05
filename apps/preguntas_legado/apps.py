from django.apps import AppConfig


class PreguntasLegadoConfig(AppConfig):
    """
    App sin modelos que solo conserva el historial de migraciones de la antigua
    app `preguntas` (etiqueta "preguntas"). Sus tablas pertenecen ahora a
    banco_preguntas, cuestionarios, importaciones y evaluaciones; la migración
    0003 traspasó el estado sin tocar la base de datos.

    No eliminar: en una base nueva, su 0001 es la que crea esas tablas.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.preguntas_legado"
    label = "preguntas"
    verbose_name = "Migraciones heredadas de preguntas"
