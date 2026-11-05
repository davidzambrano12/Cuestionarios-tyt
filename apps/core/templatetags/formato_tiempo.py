from django import template

register = template.Library()


@register.filter
def duracion(segundos):
    """Convierte segundos en un texto legible: '1 h 05 min', '12 min 34 s', '45 s'."""
    try:
        total = int(segundos)
    except (TypeError, ValueError):
        return "—"
    if total <= 0:
        return "—"
    horas, resto = divmod(total, 3600)
    minutos, segs = divmod(resto, 60)
    if horas:
        return f"{horas} h {minutos:02d} min"
    if minutos:
        return f"{minutos} min {segs:02d} s"
    return f"{segs} s"
