# Pruebas

## Pruebas unitarias y de integración

Cada app tiene sus pruebas en `apps/<app>/tests/`. Usan una base de datos de prueba aparte en MariaDB, así que no tocan los datos reales.

```bash
python manage.py test
```

## Pruebas de navegador (E2E)

Están en `pruebas_e2e/` y recorren los flujos completos en un navegador real con Playwright: presentar y entregar un examen, previsualización docente, banco de preguntas, editor de cuestionarios, importación desde Excel, reporte de intentos, inicio de sesión, usuarios y roles, y ajustes.

Por defecto se **omiten**, para que `manage.py test` siga siendo rápido. Para ejecutarlas:

```bash
pip install -r requirements-dev.txt
playwright install chromium        # una sola vez; descarga el navegador de Playwright

# Linux / macOS / Git Bash
E2E=1 python manage.py test pruebas_e2e

# PowerShell
$env:E2E = "1"; python manage.py test pruebas_e2e
```

Variables opcionales:

| Variable | Uso |
|---|---|
| `E2E_NAVEGADOR` | `chromium` (por defecto), o `msedge` / `chrome` para usar un navegador ya instalado sin `playwright install`. |
| `E2E_CAPTURAS` | Carpeta donde guardar capturas de pantalla de cada flujo. |

Además de las acciones, estas pruebas verifican que el contenido de las preguntas, del Excel y de los nombres de usuario se muestre como texto y nunca se ejecute como código, y que ninguna página produzca errores de JavaScript.
