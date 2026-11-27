"""
La columna `estado` es un ENUM en el script institucional (database/pruebas-tyt.sql)
y un VARCHAR en las bases creadas por Django. Se deja como ENUM con los cinco
estados en todas, para que MariaDB/MySQL rechace cualquier otro valor.
"""
from django.db import migrations

ENUM_NUEVO = "ENUM('borrador','disponible','oculto','cerrado','archivado')"
ENUM_ANTERIOR = "ENUM('borrador','programado','disponible','cerrado')"


class Migration(migrations.Migration):

    dependencies = [
        ("cuestionarios", "0003_estados_oculto_archivado"),
    ]

    operations = [
        migrations.RunSQL(
            sql=f"ALTER TABLE cuestionarios MODIFY estado {ENUM_NUEVO} NOT NULL DEFAULT 'borrador'",
            # Al revertir, los estados nuevos vuelven a uno equivalente del ENUM anterior
            reverse_sql=[
                "UPDATE cuestionarios SET estado = 'cerrado' WHERE estado IN ('oculto', 'archivado')",
                f"ALTER TABLE cuestionarios MODIFY estado {ENUM_ANTERIOR} NOT NULL DEFAULT 'borrador'",
            ],
        ),
    ]
