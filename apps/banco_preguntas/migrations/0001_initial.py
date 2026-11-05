"""
Estado inicial de banco_preguntas (tablas categorias, preguntas, opciones_respuesta).

Migración de SOLO ESTADO: las tablas ya existen en MariaDB (las creó la
app heredada `preguntas` en su 0001). Aquí únicamente se traspasa la
propiedad de los modelos en el estado de Django, sin ejecutar SQL.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("preguntas", "0003_traspasar_modelos_a_apps"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Categoria',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('nombre', models.CharField(max_length=150)),
                        ('descripcion', models.TextField(blank=True, null=True)),
                        ('creado_en', models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        'db_table': 'categorias',
                    },
                ),
                migrations.CreateModel(
                    name='Pregunta',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('tipo', models.CharField(choices=[('MULTIPLE', 'Selección múltiple'), ('V_F', 'Verdadero / Falso')], max_length=10)),
                        ('texto_base', models.TextField(blank=True, null=True)),
                        ('enunciado', models.TextField()),
                        ('retroalimentacion', models.TextField(blank=True, null=True)),
                        ('puntaje', models.DecimalField(decimal_places=2, default=1, max_digits=6)),
                        ('huella_contenido', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                        ('activa', models.BooleanField(default=True)),
                        ('categoria', models.ForeignKey(db_column='categoria_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='preguntas', to='banco_preguntas.categoria')),
                    ],
                    options={
                        'db_table': 'preguntas',
                    },
                ),
                migrations.CreateModel(
                    name='OpcionRespuesta',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('texto', models.CharField(max_length=500)),
                        ('es_correcta', models.BooleanField(default=False)),
                        ('orden', models.SmallIntegerField(default=0)),
                        ('pregunta', models.ForeignKey(db_column='pregunta_id', on_delete=django.db.models.deletion.CASCADE, related_name='opciones', to='banco_preguntas.pregunta')),
                    ],
                    options={
                        'db_table': 'opciones_respuesta',
                    },
                ),
    
            ],
        ),
    ]
