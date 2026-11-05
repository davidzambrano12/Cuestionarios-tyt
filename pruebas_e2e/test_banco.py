"""Banco de preguntas: crear (múltiple y V/F), editar, filtrar y accesos directos."""
from apps.banco_preguntas.models import Categoria, Pregunta
from apps.core.tests.factories import crear_usuario, sembrar_roles

from .base import PruebaNavegador


class BancoTests(PruebaNavegador):
    def setUp(self):
        sembrar_roles()
        self.docente = crear_usuario("prof", "docente")
        Categoria.objects.create(nombre="Lectura Crítica")
        Categoria.objects.create(nombre="Inglés")

    def test_crear_editar_y_filtrar(self):
        pg, errores = self.abrir("/preguntas/#nueva", self.docente)
        self.assertTrue(self.modal_abierto(pg, "modal-pregunta"))  # #nueva abre el modal

        # Verdadero/Falso: las opciones múltiples ocultas no deben bloquear el envío
        pg.select_option("#campo-tipo", "V_F")
        pg.fill("#campo-enunciado", "El sol es una estrella")
        pg.check('[name="correcta_vf"][value="F"]')
        pg.click('[data-ref="guardar"]')
        pg.wait_for_load_state("networkidle")
        vf = Pregunta.objects.get(tipo="V_F")
        self.assertEqual(
            [(o.texto, o.es_correcta) for o in vf.opciones.order_by("orden")],
            [("Verdadero", False), ("Falso", True)],
        )

        # Selección múltiple
        pg.click('.encabezado-pagina [data-accion="nueva"]')
        self.assertEqual(pg.input_value("#campo-enunciado"), "")
        pg.select_option("#campo-categoria", label="Inglés")
        pg.fill("#campo-enunciado", "Choose the correct option")
        for letra in "ABCD":
            pg.fill(f"#opcion-{letra}", f"Option {letra}")
        pg.check("#correcta-C")
        pg.click('[data-ref="guardar"]')
        pg.wait_for_load_state("networkidle")
        multiple = Pregunta.objects.get(tipo="MULTIPLE")
        self.assertTrue(multiple.opciones.get(orden=3).es_correcta)

        # Editar: el modal carga los datos
        pg.click(f'[data-editar="{multiple.id}"]')
        pg.wait_for_function("document.getElementById('campo-enunciado').value !== ''")
        self.assertEqual(pg.input_value("#opcion-C"), "Option C")
        self.assertTrue(pg.is_checked("#correcta-C"))
        pg.fill("#campo-enunciado", "Choose the right option")
        pg.click('[data-ref="guardar"]')
        pg.wait_for_load_state("networkidle")
        multiple.refresh_from_db()
        self.assertEqual(multiple.enunciado, "Choose the right option")

        # Filtros y estado vacío
        pg.select_option("#filtro-tipo", "V_F")
        self.assertEqual(pg.locator(".pregunta-card:visible").count(), 1)
        pg.fill("#filtro-pregunta", "zzz")
        self.assertTrue(pg.is_visible("#sin-resultados"))
        pg.click('#sin-resultados [data-accion="limpiar-filtros"]')
        self.assertEqual(pg.locator(".pregunta-card:visible").count(), 2)
        self.capturar(pg, "banco")
        self.assertEqual(errores, [])

    def test_acceso_directo_a_editar(self):
        pregunta = Pregunta.objects.create(
            categoria=Categoria.objects.first(), tipo="MULTIPLE", enunciado="Desde la previsualización", puntaje=1,
        )
        pg, errores = self.abrir(f"/preguntas/?editar={pregunta.id}", self.docente)
        pg.wait_for_function("document.getElementById('campo-enunciado').value === 'Desde la previsualización'")
        self.assertIn(f"P-{pregunta.id}", pg.inner_text('#modal-pregunta [data-ref="subtitulo"]'))
        pg.keyboard.press("Escape")
        self.assertFalse(self.modal_abierto(pg, "modal-pregunta"))
        self.assertEqual(errores, [])
