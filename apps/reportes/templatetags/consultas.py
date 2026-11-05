"""Enlaces de la pantalla de consultas que conservan los filtros activos."""
from django import template

register = template.Library()


@register.simple_tag
def con_filtros(filtros, **cambios):
    """Querystring con los filtros actuales y los cambios indicados (p. ej. vista, page)."""
    cambios = {k: ("" if v is None else v) for k, v in cambios.items()}
    if "vista" in cambios and "page" not in cambios:
        cambios["page"] = ""  # al cambiar de vista se vuelve a la primera página
    texto = filtros.querystring(**cambios)
    return f"?{texto}" if texto else "?"


@register.filter
def nota(valor):
    """Nota con dos decimales y coma decimal; «—» si no hay."""
    if valor is None or valor == "":
        return "—"
    return f"{valor:.2f}".replace(".", ",")


@register.filter
def porcentaje(valor):
    if valor is None:
        return "—"
    return f"{valor:.1f} %".replace(".", ",")
