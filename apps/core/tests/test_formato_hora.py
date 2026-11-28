"""La hora se muestra en formato de 12 horas en toda la aplicación."""
from datetime import datetime

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import timezone

from apps.core.templatetags.formato_tiempo import hora_12


class HoraDoceTests(SimpleTestCase):
    def test_tarde_mediodia_y_medianoche(self):
        self.assertEqual(hora_12(datetime(2026, 11, 27, 14, 5)), "2:05 p. m.")
        self.assertEqual(hora_12(datetime(2026, 11, 27, 12, 0)), "12:00 p. m.")
        self.assertEqual(hora_12(datetime(2026, 11, 27, 0, 30)), "12:30 a. m.")
        self.assertEqual(hora_12(datetime(2026, 11, 27, 9, 0)), "9:00 a. m.")

    def test_filtro_usa_la_hora_local_y_tolera_vacios(self):
        momento = timezone.make_aware(datetime(2026, 11, 27, 18, 45))
        salida = Template("{% load formato_tiempo %}{{ m|hora }}|{{ n|hora }}").render(Context({"m": momento, "n": None}))
        self.assertEqual(salida, "6:45 p. m.|")
