"""El curso universitario es una asignatura dictada a un grupo, no un grado escolar."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def crear_permiso(apps, schema_editor):
    PermisoSistema = apps.get_model("core", "PermisoSistema")
    Rol = apps.get_model("core", "Rol")
    permiso, _ = PermisoSistema.objects.update_or_create(
        codigo="cursos.gestionar",
        defaults={"nombre": "Gestionar cursos y matrículas",
                  "descripcion": "Permite crear cursos y matricular estudiantes (el docente, solo en sus cursos)",
                  "modulo": "Cursos"},
    )
    for rol in Rol.objects.filter(codigo__in=["admin", "docente"]):
        rol.permisos.add(permiso)


def quitar_permiso(apps, schema_editor):
    apps.get_model("core", "PermisoSistema").objects.filter(codigo="cursos.gestionar").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0001_initial"),
        ("core", "0002_configuracion_sistema"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="curso", name="uq_curso_periodo_nombre"),
        migrations.RenameField(model_name="curso", old_name="nombre", new_name="asignatura"),
        migrations.AlterField(
            model_name="curso", name="asignatura",
            field=models.CharField(help_text="Ej.: Electiva Profesional III – Frameworks", max_length=150),
        ),
        migrations.AddField(
            model_name="curso", name="grupo",
            field=models.CharField(default="01", help_text="Ej.: 01, 02, A", max_length=10),
        ),
        migrations.AddField(
            model_name="curso", name="semestre",
            field=models.PositiveSmallIntegerField(blank=True, null=True, help_text="Semestre del plan de estudios (1 a 12)."),
        ),
        migrations.AlterField(
            model_name="curso", name="docente",
            field=models.ForeignKey(
                blank=True, db_column="docente_id", help_text="Docente que gestiona el curso y consulta sus resultados.",
                null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cursos_a_cargo",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="curso", options={"ordering": ["-periodo__anio", "-periodo__numero", "asignatura", "grupo"]},
        ),
        migrations.AddConstraint(
            model_name="curso",
            constraint=models.UniqueConstraint(fields=("periodo", "asignatura", "grupo"), name="uq_curso_periodo_asignatura_grupo"),
        ),
        migrations.AddConstraint(
            model_name="curso",
            constraint=models.CheckConstraint(
                condition=models.Q(("semestre__isnull", True), models.Q(("semestre__gte", 1), ("semestre__lte", 12)), _connector="OR"),
                name="chk_curso_semestre",
            ),
        ),
        migrations.RunPython(crear_permiso, quitar_permiso),
    ]
