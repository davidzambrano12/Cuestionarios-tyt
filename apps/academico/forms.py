from django import forms
from django.contrib.auth.models import User

from .models import Curso, PeriodoAcademico


class PeriodoForm(forms.ModelForm):
    class Meta:
        model = PeriodoAcademico
        fields = ["anio", "numero", "fecha_inicio", "fecha_fin"]
        labels = {"anio": "Año", "numero": "Número del período", "fecha_inicio": "Inicio", "fecha_fin": "Fin"}
        help_texts = {"numero": "1 o 2 en semestres (2026-1, 2026-2)."}
        widgets = {
            "anio": forms.NumberInput(attrs={"class": "form-input", "min": 2000, "max": 2100}),
            "numero": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 4}),
            "fecha_inicio": forms.DateInput(attrs={"class": "form-input", "type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"class": "form-input", "type": "date"}, format="%Y-%m-%d"),
        }


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ["periodo", "asignatura", "grupo", "programa", "semestre", "docente", "activo"]
        labels = {"periodo": "Período académico", "semestre": "Semestre", "activo": "Curso activo"}
        help_texts = {
            "grupo": "Identificador del grupo de la asignatura: 01, 02…",
            "activo": "Los cursos inactivos no reciben intentos nuevos, pero conservan su historial.",
        }
        widgets = {
            "periodo": forms.Select(attrs={"class": "form-select"}),
            "asignatura": forms.TextInput(attrs={"class": "form-input", "placeholder": "Ej.: Electiva Profesional III – Frameworks"}),
            "grupo": forms.TextInput(attrs={"class": "form-input"}),
            "programa": forms.TextInput(attrs={"class": "form-input"}),
            "semestre": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 12}),
            "docente": forms.Select(attrs={"class": "form-select"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def __init__(self, *args, puede_elegir_docente: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["periodo"].queryset = PeriodoAcademico.objects.order_by("-anio", "-numero")
        self.fields["periodo"].empty_label = "Selecciona un período"
        if puede_elegir_docente:
            self.fields["docente"].queryset = User.objects.filter(
                is_active=True, perfil__rol__codigo__in=["docente", "docente_evaluador", "admin"],
            ).order_by("first_name", "last_name")
            self.fields["docente"].label_from_instance = lambda u: u.get_full_name() or u.username
            self.fields["docente"].empty_label = "Sin docente asignado"
        else:
            # El docente crea y edita solo cursos a su cargo
            del self.fields["docente"]
