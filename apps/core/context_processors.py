"""Variables disponibles en todas las plantillas."""
from django.utils.functional import SimpleLazyObject

from apps.core.models import ConfiguracionSistema


def configuracion(request):
    # Perezoso: solo consulta la base si la plantilla usa {{ config }}
    return {"config": SimpleLazyObject(ConfiguracionSistema.actual)}
