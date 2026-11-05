"""Tag {% componente %} y plantillas de templates/componentes/."""
from django.template import Context, Template, TemplateSyntaxError
from django.test import SimpleTestCase


def render(fuente, **contexto):
    return Template("{% load componentes %}" + fuente).render(Context(contexto))


class ComponentesTests(SimpleTestCase):
    def test_encabezado_con_acciones(self):
        html = render(
            '{% componente "componentes/encabezado.html" etiqueta="Reportes" titulo=nombre %}'
            '<a class="btn" href="/x/">Volver</a>{% fincomponente %}',
            nombre="Simulacro 1",
        )
        self.assertIn('<h1 class="banner-title">Simulacro 1</h1>', html)
        self.assertIn('<span class="banner-badge">Reportes</span>', html)
        self.assertIn('<a class="btn" href="/x/">Volver</a>', html)  # el slot no se escapa

    def test_parametros_se_escapan(self):
        html = render('{% componente "componentes/encabezado.html" titulo=t %}{% fincomponente %}', t="<script>")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("encabezado-pagina__acciones", html)  # sin slot no hay contenedor de acciones

    def test_metrica_con_variante_y_sufijo(self):
        html = render(
            '{% componente "componentes/metrica.html" etiqueta="Aprobados" valor=3 variante="exito" %}de 5{% fincomponente %}'
        )
        self.assertIn("metrica--exito", html)
        self.assertIn('<span class="metrica__sufijo">de 5</span>', html)

    def test_estado_vacio(self):
        html = render('{% componente "componentes/estado_vacio.html" titulo="Sin datos" %}{% fincomponente %}')
        self.assertIn('data-lucide="inbox"', html)
        self.assertIn("Sin datos", html)

    def test_parametro_mal_formado(self):
        with self.assertRaises(TemplateSyntaxError):
            render('{% componente "componentes/encabezado.html" titulo %}{% fincomponente %}')
