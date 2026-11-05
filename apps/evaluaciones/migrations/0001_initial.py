"""
Estado inicial de evaluaciones (tablas intentos, respuestas_intento).

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
        ('cuestionarios', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Intento',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('participante_nombre', models.CharField(max_length=150)),
                        ('participante_codigo', models.CharField(max_length=50)),
                        ('fecha_inicio', models.DateTimeField(auto_now_add=True)),
                        ('fecha_fin', models.DateTimeField(blank=True, null=True)),
                        ('duracion_segundos', models.IntegerField(blank=True, null=True)),
                        ('puntaje_obtenido', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                        ('puntaje_total_posible', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                        ('calificacion', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                        ('aprobado', models.BooleanField(blank=True, null=True)),
                        ('estado', models.CharField(choices=[('en_progreso', 'En progreso'), ('finalizado', 'Finalizado'), ('vencido', 'Vencido')], default='en_progreso', max_length=20)),
                        ('cuestionario', models.ForeignKey(db_column='cuestionario_id', on_delete=django.db.models.deletion.CASCADE, related_name='intentos', to='cuestionarios.cuestionario')),
                    ],
                    options={
                        'db_table': 'intentos',
                    },
                ),
                migrations.CreateModel(
                    name='RespuestaIntento',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('es_correcta', models.BooleanField(blank=True, null=True)),
                        ('puntaje_obtenido', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                        ('marcada_para_revision', models.BooleanField(default=False)),
                        ('intento', models.ForeignKey(db_column='intento_id', on_delete=django.db.models.deletion.CASCADE, related_name='respuestas', to='evaluaciones.intento')),
                        ('opcion_seleccionada', models.ForeignKey(blank=True, db_column='opcion_seleccionada_id', null=True, on_delete=django.db.models.deletion.SET_NULL, to='banco_preguntas.opcionrespuesta')),
                        ('pregunta', models.ForeignKey(db_column='pregunta_id', on_delete=django.db.models.deletion.CASCADE, related_name='respuestas_intento', to='banco_preguntas.pregunta')),
                    ],
                    options={
                        'db_table': 'respuestas_intento',
                    },
                ),
    
            ],
        ),
    ]
