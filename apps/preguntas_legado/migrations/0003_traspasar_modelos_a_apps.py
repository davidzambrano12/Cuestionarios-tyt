"""
Traspasa los modelos de `preguntas` a sus nuevas apps.

Migración de SOLO ESTADO: las tablas ya existen en MariaDB (las creó la
app heredada `preguntas` en su 0001). Aquí únicamente se traspasa la
propiedad de los modelos en el estado de Django, sin ejecutar SQL.
"""

from django.db import migrations


# Modelo -> app que lo posee ahora. Mantiene los permisos y el historial del
# admin apuntando al mismo registro de django_content_type.
NUEVO_DUENO = {
    "categoria": "banco_preguntas",
    "pregunta": "banco_preguntas",
    "opcionrespuesta": "banco_preguntas",
    "cuestionario": "cuestionarios",
    "cuestionariopregunta": "cuestionarios",
    "importacion": "importaciones",
    "intento": "evaluaciones",
    "respuestaintento": "evaluaciones",
}


def traspasar_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for modelo, app in NUEVO_DUENO.items():
        viejo = ContentType.objects.filter(app_label="preguntas", model=modelo)
        if ContentType.objects.filter(app_label=app, model=modelo).exists():
            # Bases que ya tenían ese content type (de una estructura anterior):
            # se conserva el existente y se descarta el duplicado de `preguntas`
            # junto con sus permisos automáticos.
            viejo.delete()
        else:
            viejo.update(app_label=app)


def devolver_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for modelo, app in NUEVO_DUENO.items():
        ContentType.objects.filter(app_label=app, model=modelo).update(app_label="preguntas")


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ('preguntas', '0002_alter_cuestionario_intentos_permitidos'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name='pregunta',
                    name='categoria',
                ),
                migrations.RemoveField(
                    model_name='importacion',
                    name='cuestionario',
                ),
                migrations.RemoveField(
                    model_name='cuestionariopregunta',
                    name='cuestionario',
                ),
                migrations.RemoveField(
                    model_name='intento',
                    name='cuestionario',
                ),
                migrations.AlterUniqueTogether(
                    name='cuestionariopregunta',
                    unique_together=None,
                ),
                migrations.RemoveField(
                    model_name='cuestionariopregunta',
                    name='pregunta',
                ),
                migrations.RemoveField(
                    model_name='respuestaintento',
                    name='intento',
                ),
                migrations.RemoveField(
                    model_name='opcionrespuesta',
                    name='pregunta',
                ),
                migrations.RemoveField(
                    model_name='respuestaintento',
                    name='opcion_seleccionada',
                ),
                migrations.RemoveField(
                    model_name='respuestaintento',
                    name='pregunta',
                ),
                migrations.DeleteModel(
                    name='Categoria',
                ),
                migrations.DeleteModel(
                    name='Importacion',
                ),
                migrations.DeleteModel(
                    name='Cuestionario',
                ),
                migrations.DeleteModel(
                    name='CuestionarioPregunta',
                ),
                migrations.DeleteModel(
                    name='Intento',
                ),
                migrations.DeleteModel(
                    name='OpcionRespuesta',
                ),
                migrations.DeleteModel(
                    name='Pregunta',
                ),
                migrations.DeleteModel(
                    name='RespuestaIntento',
                ),
    
            ],
        ),
        migrations.RunPython(traspasar_content_types, devolver_content_types),
    ]
