"""
Selección del entorno de configuración.

Las variables se leen de `.env` (ver `.env.example`). `DJANGO_ENV` decide
el módulo: `dev` (por defecto) o `prod`.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

if os.environ.get("DJANGO_ENV", "dev").lower() == "prod":
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
