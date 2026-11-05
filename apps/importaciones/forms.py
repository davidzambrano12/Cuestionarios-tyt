from django.core.exceptions import ValidationError
from django import forms
from apps.cuestionarios.models import Cuestionario

EXTENSIONES_VALIDAS = (".xlsx", ".xlsm")


class ImportarPreguntasForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo Excel (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx,.xlsm", "class": "zona-archivo__input"}),
    )
    cuestionario = forms.ModelChoiceField(
        queryset=Cuestionario.objects.all(),
        required=False,
        label="Cuestionario de destino",
        empty_label="Ninguno: solo agregar al banco de preguntas",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None:
            from apps.cuestionarios.acceso import editables

            # Solo se importan preguntas hacia cuestionarios que el usuario gestiona
            self.fields["cuestionario"].queryset = editables(usuario).order_by("-id")

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        nombre = archivo.name.lower()
        if not nombre.endswith(EXTENSIONES_VALIDAS):
            raise ValidationError("El archivo debe ser .xlsx (Excel).")
        limite_mb = 5
        if archivo.size > limite_mb * 1024 * 1024:
            raise ValidationError(f"El archivo supera el límite de {limite_mb} MB.")
        return archivo

