"""
Estado inicial de importaciones (tabla importaciones).

Migración de SOLO ESTADO: las tablas ya existen en MariaDB (las creó la
app heredada `preguntas` en su 0001). Aquí únicamente se traspasa la
propiedad de los modelos en el estado de Django, sin ejecutar SQL.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cuestionarios', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Importacion',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('nombre_archivo', models.CharField(max_length=255)),
                        ('fecha', models.DateTimeField(auto_now_add=True)),
                        ('total_filas', models.IntegerField(default=0)),
                        ('filas_validas', models.IntegerField(default=0)),
                        ('filas_duplicadas', models.IntegerField(default=0)),
                        ('filas_con_error', models.IntegerField(default=0)),
                        ('resultado', models.CharField(choices=[('exitosa', 'Exitosa'), ('parcial', 'Parcial'), ('fallida', 'Fallida')], max_length=10)),
                        ('cuestionario', models.ForeignKey(blank=True, db_column='cuestionario_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='importaciones', to='cuestionarios.cuestionario')),
                    ],
                    options={
                        'db_table': 'importaciones',
                    },
                ),
    
            ],
        ),
    ]
