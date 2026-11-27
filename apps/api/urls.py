from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views

app_name = "api"

urlpatterns = [
    # Documentación OpenAPI
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),

    # Operaciones
    path("simulacros/", views.SimulacroListView.as_view(), name="simulacros"),
    path("preguntas/", views.PreguntaListView.as_view(), name="preguntas"),
    path("preguntas/<int:pk>/", views.PreguntaDetalleView.as_view(), name="pregunta"),
    path("intentos/", views.IntentoCrearView.as_view(), name="intentos"),
    path("intentos/<int:pk>/finalizar/", views.IntentoFinalizarView.as_view(), name="intento_finalizar"),
    path("resultados/", views.ResultadoListView.as_view(), name="resultados"),
    path("reportes/", views.ReporteView.as_view(), name="reportes"),
]
