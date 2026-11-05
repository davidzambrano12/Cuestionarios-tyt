"""
Componentes de interfaz reutilizables con contenido interno ("slot").

Uso:
    {% load componentes %}
    {% componente "componentes/encabezado.html" etiqueta="Reportes" titulo=cuestionario.nombre %}
        <a class="btn btn-primary" href="...">Volver</a>
    {% fincomponente %}

La plantilla del componente recibe los parámetros como variables y el HTML
interior ya renderizado en `contenido`. El contexto de la página no se
filtra al componente salvo `request`, `user` y `csrf_token`.
"""
from django import template
from django.template.loader import get_template
from django.utils.safestring import mark_safe

register = template.Library()

CONTEXTO_HEREDADO = ("request", "user", "csrf_token", "perms")


class NodoComponente(template.Node):
    def __init__(self, nombre, parametros, interior):
        self.nombre = nombre
        self.parametros = parametros
        self.interior = interior

    def render(self, context):
        datos = {clave: context.get(clave) for clave in CONTEXTO_HEREDADO if clave in context}
        datos.update({clave: valor.resolve(context) for clave, valor in self.parametros.items()})
        # El interior ya fue renderizado (y escapado) por el motor de plantillas
        datos["contenido"] = mark_safe(self.interior.render(context).strip())
        return get_template(self.nombre.resolve(context)).render(datos)


@register.tag("componente")
def componente(parser, token):
    partes = token.split_contents()
    if len(partes) < 2:
        raise template.TemplateSyntaxError("{% componente %} necesita la ruta de la plantilla.")
    nombre = parser.compile_filter(partes[1])
    parametros = {}
    for parte in partes[2:]:
        if "=" not in parte:
            raise template.TemplateSyntaxError(f"Parámetro inválido en {{% componente %}}: {parte}")
        clave, valor = parte.split("=", 1)
        parametros[clave] = parser.compile_filter(valor)
    interior = parser.parse(("fincomponente",))
    parser.delete_first_token()
    return NodoComponente(nombre, parametros, interior)
