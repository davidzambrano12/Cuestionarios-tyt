"""
Estado inicial de cuestionarios (tablas cuestionarios, cuestionario_preguntas).

Migración de SOLO ESTADO: las tablas ya existen en MariaDB (las creó la
app heredada `preguntas` en su 0001). Aquí únicamente se traspasa la
propiedad de los modelos en el estado de Django, sin ejecutar SQL.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('banco_preguntas', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Cuestionario',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('nombre', models.CharField(max_length=200)),
                        ('descripcion', models.TextField(blank=True, null=True)),
                        ('fecha_apertura', models.DateTimeField()),
                        ('fecha_cierre', models.DateTimeField()),
                        ('tiempo_limite_minutos', models.IntegerField()),
                        ('intentos_permitidos', models.IntegerField(default=5)),
                        ('calificacion_maxima', models.DecimalField(decimal_places=2, max_digits=5)),
                        ('calificacion_aprobacion', models.DecimalField(decimal_places=2, max_digits=5)),
                        ('mezclar_preguntas', models.BooleanField(default=False)),
                        ('mezclar_respuestas', models.BooleanField(default=False)),
                        ('permitir_revision', models.BooleanField(default=True)),
                        ('estado', models.CharField(choices=[('borrador', 'Borrador'), ('programado', 'Programado'), ('disponible', 'Disponible'), ('cerrado', 'Cerrado')], default='borrador', max_length=12)),
                    ],
                    options={
                        'db_table': 'cuestionarios',
                    },
                ),
                migrations.CreateModel(
                    name='CuestionarioPregunta',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('orden', models.IntegerField(default=0)),
                        ('puntaje_asignado', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                        ('cuestionario', models.ForeignKey(db_column='cuestionario_id', on_delete=django.db.models.deletion.CASCADE, related_name='cuestionario_preguntas', to='cuestionarios.cuestionario')),
                        ('pregunta', models.ForeignKey(db_column='pregunta_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='cuestionario_preguntas', to='banco_preguntas.pregunta')),
                    ],
                    options={
                        'db_table': 'cuestionario_preguntas',
                        'unique_together': {('cuestionario', 'pregunta')},
                    },
                ),
    
            ],
        ),
    ]
