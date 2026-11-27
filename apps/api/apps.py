from django.apps import AppConfig


class ApiConfig(AppConfig):
    """API REST documentada con OpenAPI (Swagger) sobre la lógica de las demás apps."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    verbose_name = "API REST"
