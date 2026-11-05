from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cuentas"
    label = "cuentas"
    verbose_name = "Cuentas: autenticación, perfil y gestión de usuarios"
