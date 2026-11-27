# Simulador Saber TyT

Plataforma web de Uniputumayo para preparar a los estudiantes en las competencias de las pruebas Saber TyT: banco de preguntas, importación desde Excel, simulacros con temporizador, calificación inmediata, reportes y una API REST documentada con Swagger.

**Tecnologías:** Python 3.12+, Django 6.1, Django REST Framework, drf-spectacular, MariaDB (PyMySQL).

## Estructura

| Carpeta | Contenido |
|---|---|
| `config/` | Configuración (`settings/base.py`, `dev.py`, `prod.py`), URLs y WSGI |
| `apps/core` | Roles, permisos, perfiles y servicios de acceso |
| `apps/cuentas` | Inicio de sesión, usuarios, roles y tokens JWT |
| `apps/academico` | Períodos, cursos y matrículas |
| `apps/banco_preguntas` | Categorías (ejes) y preguntas |
| `apps/importaciones` | Carga masiva de preguntas desde Excel |
| `apps/cuestionarios` | Configuración de simulacros |
| `apps/evaluaciones` | Presentación y calificación de intentos |
| `apps/reportes` | Consultas por año, curso y eje |
| `apps/api` | API REST y documentación Swagger |
| `templates/`, `static/` | Interfaz web |
| `pruebas_e2e/` | Pruebas de navegador con Playwright |

## Instalación local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # completar DB_PASSWORD y DJANGO_SECRET_KEY
python manage.py migrate
python manage.py seed_data         # permisos, roles y usuarios de demostración
python manage.py datos_demo_consultas   # opcional: cursos e intentos de ejemplo
python manage.py runserver
```

La base de datos debe existir antes de migrar (`CREATE DATABASE simulador_tyt CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`).

## API REST

- Documentación interactiva: `/api/docs/`
- Esquema OpenAPI: `/api/schema/`

Para probarla: `POST /api/auth/token/` con usuario y contraseña, copiar el valor `access` y pegarlo en **Authorize**. Sin token la API responde 401; con un rol sin permiso, 403.

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/simulacros/` | Simulacros visibles para el usuario |
| GET | `/api/preguntas/` | Banco de preguntas (docente o administrador) |
| GET, PATCH | `/api/preguntas/{id}/` | Consultar o editar una pregunta |
| POST | `/api/intentos/` | Iniciar (y opcionalmente calificar) un intento |
| POST | `/api/intentos/{id}/finalizar/` | Entregar un intento |
| GET | `/api/resultados/` | Calificaciones según el rol |
| GET | `/api/reportes/` | Indicadores filtrados por `anio`, `curso` y `eje` |

## Pruebas

```bash
python manage.py test
```

Ver `docs/pruebas.md` para las pruebas de navegador.

## Despliegue en Vercel

Vercel detecta el proyecto Django por `manage.py` y usa `WSGI_APPLICATION` (`config.wsgi.application`). Como `STATIC_ROOT` está definido, ejecuta `collectstatic` durante el build y sirve `/static/` desde su CDN. La versión de Python se toma de `.python-version`.

1. Crear la base MariaDB/MySQL en la nube con TLS y cargar los datos (`mysqldump` local e importación en el servidor, o `migrate` + `seed_data` apuntando a la base remota).
2. Importar el repositorio en Vercel y definir estas variables de entorno (**Settings → Environment Variables**):

| Variable | Valor |
|---|---|
| `DJANGO_ENV` | `prod` |
| `DJANGO_SECRET_KEY` | Clave nueva y larga, distinta de la local |
| `DJANGO_ALLOWED_HOSTS` | `<proyecto>.vercel.app` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Opcional; por defecto `https://` + cada host |
| `DJANGO_MEDIA_ROOT` | `/tmp/media` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Datos de la base en la nube |
| `DB_SSL` | `True` |
| `DB_SSL_CA` | Ruta al certificado CA del proveedor (si lo exige); si se omite se usan las autoridades públicas |

3. Desplegar y comprobar `/`, `/login/` y `/api/docs/`.

En producción `DEBUG` es siempre `False`, las cookies son seguras, se fuerza HTTPS y las credenciales nunca están en el código: todo se lee de variables de entorno.

**Limitación conocida:** en Vercel solo `/tmp` admite escritura y no se comparte entre instancias, por lo que la importación desde Excel (que guarda el archivo entre pasos) puede fallar ahí. El resto de la aplicación no escribe en disco.
