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


@register.filter
def tiempo_relativo(momento):
    """Fecha pasada en lenguaje corriente: 'Hace 5 min', 'Hace 3 h', 'Ayer', 'Hace 12 días', '3 mar 2026'."""
    if not momento:
        return "—"
    from django.utils import timezone
    from django.utils.formats import date_format

    segundos = (timezone.now() - momento).total_seconds()
    if segundos < 60:
        return "Hace un momento"
    if segundos < 3600:
        return f"Hace {int(segundos // 60)} min"
    if segundos < 86400:
        return f"Hace {int(segundos // 3600)} h"
    dias = int(segundos // 86400)
    if dias == 1:
        return "Ayer"
    if dias < 30:
        return f"Hace {dias} días"
    return date_format(timezone.localtime(momento), "j M Y")


def hora_12(momento) -> str:
    """Hora local en formato de 12 horas: '2:30 p. m.', '9:05 a. m.'."""
    from django.utils import timezone

    if timezone.is_aware(momento):
        momento = timezone.localtime(momento)
    sufijo = "a. m." if momento.hour < 12 else "p. m."
    return f"{(momento.hour % 12) or 12}:{momento.minute:02d} {sufijo}"


@register.filter
def hora(momento):
    """Filtro de plantilla para `hora_12`: la hora siempre en 12 horas en toda la app."""
    if not momento:
        return ""
    return hora_12(momento)
