from django.contrib import admin

from .models import Curso, Matricula, PeriodoAcademico


class CursoInline(admin.TabularInline):
    model = Curso
    extra = 0
    fields = ("nombre", "programa", "docente", "activo")


@admin.register(PeriodoAcademico)
class PeriodoAcademicoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "anio", "numero", "fecha_inicio", "fecha_fin")
    list_filter = ("anio",)
    inlines = [CursoInline]


class MatriculaInline(admin.TabularInline):
    model = Matricula
    extra = 1
    autocomplete_fields = ("estudiante",)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "periodo", "programa", "docente", "activo", "num_matriculados")
    list_filter = ("periodo__anio", "periodo", "activo")
    search_fields = ("nombre", "programa")
    autocomplete_fields = ("docente",)
    inlines = [MatriculaInline]

    @admin.display(description="Matriculados")
    def num_matriculados(self, obj):
        return obj.matriculas.count()


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "curso", "fecha_matricula")
    list_filter = ("curso__periodo", "curso")
    search_fields = ("estudiante__username", "estudiante__first_name", "estudiante__last_name",
                     "estudiante__perfil__codigo_institucional")
    autocomplete_fields = ("estudiante", "curso")
