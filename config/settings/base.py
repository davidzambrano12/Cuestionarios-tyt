"""
Configuración común a todos los entornos del Simulador Saber TyT.

Los valores sensibles (clave secreta, credenciales de MariaDB, hosts) se leen
de variables de entorno cargadas desde `.env`. Ver `.env.example`.
"""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# DEBUG, SECRET_KEY y ALLOWED_HOSTS se definen en dev.py / prod.py
DEBUG = False

# Botones de acceso rápido con usuarios de demostración en el login
# (solo para la sustentación; nunca en producción)
MOSTRAR_ACCESOS_DEMO = False


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    # Apps del proyecto (las dependencias van de arriba hacia abajo)
    "apps.core",
    "apps.cuentas",
    "apps.academico",
    "apps.banco_preguntas",
    "apps.cuestionarios",
    "apps.importaciones",
    "apps.evaluaciones",
    "apps.reportes",
    "apps.api",
    "apps.preguntas_legado",  # solo historial de migraciones; ver su apps.py
]
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # La sesión del navegador permite probar la API en Swagger sin copiar el token
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Documentación OpenAPI / Swagger (drf-spectacular): /api/docs/ y /api/schema/
SPECTACULAR_SETTINGS = {
    'TITLE': 'API Simulador Saber TyT',
    'DESCRIPTION': (
        'API REST del Simulador Saber TyT (Uniputumayo).\n\n'
        '**Cómo autenticarse:** obtenga un token con `POST /api/auth/token/` (usuario o correo y '
        'contraseña), pulse **Authorize** y pegue el valor de `access`. También funciona la '
        'sesión iniciada en el navegador.\n\n'
        'Los permisos son los mismos de la aplicación web: cada rol solo ve y modifica lo que '
        'le corresponde.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/api/',
    'COMPONENT_SPLIT_REQUEST': True,
    'TAGS': [
        {'name': 'Autenticación', 'description': 'Tokens JWT de acceso.'},
        {'name': 'Simulacros', 'description': 'Cuestionarios publicados.'},
        {'name': 'Preguntas', 'description': 'Banco de preguntas (docentes y administradores).'},
        {'name': 'Intentos', 'description': 'Presentar un simulacro (estudiantes).'},
        {'name': 'Resultados', 'description': 'Calificaciones según el rol.'},
        {'name': 'Reportes', 'description': 'Consultas filtradas por año, curso y eje temático.'},
    ],
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
        'displayRequestDuration': True,
        'filter': True,
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.cuentas.middleware.JWTAuthCookieMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.configuracion",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "simulador_tyt"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "es-co"

TIME_ZONE = "America/Bogota"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

# Redirecciones de Autenticación
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "evaluaciones:panel_estudiante"
LOGOUT_REDIRECT_URL = "login"

