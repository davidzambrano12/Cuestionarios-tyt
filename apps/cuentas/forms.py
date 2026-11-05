from django import forms

from apps.core.models import ConfiguracionSistema


class AjustesForm(forms.ModelForm):
    """Datos institucionales que el administrador puede cambiar."""

    class Meta:
        model = ConfiguracionSistema
        fields = ["nombre_sistema", "institucion", "sigla", "correo_soporte", "telefono_soporte", "ubicacion"]
        widgets = {
            "nombre_sistema": forms.TextInput(attrs={"class": "form-input"}),
            "institucion": forms.TextInput(attrs={"class": "form-input"}),
            "sigla": forms.TextInput(attrs={"class": "form-input"}),
            "correo_soporte": forms.EmailInput(attrs={"class": "form-input"}),
            "telefono_soporte": forms.TextInput(attrs={"class": "form-input", "placeholder": "Ej.: (+57) 8 420 0000 ext. 104"}),
            "ubicacion": forms.TextInput(attrs={"class": "form-input"}),
        }
