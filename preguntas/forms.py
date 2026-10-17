from django.core.exceptions import ValidationError
from django import forms
from .models import Cuestionario

EXTENSIONES_VALIDAS = (".xlsx", ".xlsm")


class ImportarPreguntasForm(forms.Form):
    archivo = forms.FileField(label="Archivo Excel (.xlsx)")
    cuestionario = forms.ModelChoiceField(
        queryset=Cuestionario.objects.all(),
        required=False,
        label="Cuestionario de destino",
        empty_label="(Opcional) Solo guardar en el banco de preguntas",
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        nombre = archivo.name.lower()
        if not nombre.endswith(EXTENSIONES_VALIDAS):
            raise ValidationError("El archivo debe ser .xlsx (Excel).")
        limite_mb = 5
        if archivo.size > limite_mb * 1024 * 1024:
            raise ValidationError(f"El archivo supera el límite de {limite_mb} MB.")
        return archivo

