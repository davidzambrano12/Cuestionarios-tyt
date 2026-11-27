"""RF-15: ciclo de vida del cuestionario (publicar, ocultar, cerrar, reabrir, archivar)."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.core.tests.factories import crear_cuestionario, crear_usuario, sembrar_roles
from apps.cuestionarios import estados
from apps.cuestionarios.models import Cuestionario
from apps.evaluaciones import services as evaluacion
from apps.evaluaciones.services import panel_estudiante

C = Cuestionario


def _codigos(cuestionario):
    return [a.codigo for a in estados.acciones_disponibles(cuestionario)]


class AccionesDisponiblesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()

    def test_acciones_segun_estado(self):
        casos = {
            C.BORRADOR: ["publicar", "archivar"],
            C.PUBLICADO: ["ocultar", "cerrar"],
            C.OCULTO: ["mostrar", "cerrar"],
            C.CERRADO: ["reabrir", "archivar"],
            C.ARCHIVADO: ["desarchivar"],
        }
        for estado, esperadas in casos.items():
            with self.subTest(estado=estado):
                self.assertEqual(_codigos(crear_cuestionario(estado=estado)), esperadas)

    def test_publicado_con_plazo_vencido_solo_se_archiva(self):
        ahora = timezone.now()
        c = crear_cuestionario(fecha_apertura=ahora - timedelta(days=3), fecha_cierre=ahora - timedelta(days=1))
        self.assertEqual(c.estado_temporal, "cerrado")
        self.assertEqual(_codigos(c), ["archivar"])

    def test_estado_efectivo(self):
        ahora = timezone.now()
        futuro = crear_cuestionario(fecha_apertura=ahora + timedelta(days=1), fecha_cierre=ahora + timedelta(days=2))
        self.assertEqual(futuro.estado_temporal, "programado")
        self.assertEqual(crear_cuestionario(estado=C.OCULTO).estado_temporal, "oculto")
        self.assertEqual(crear_cuestionario(estado=C.CERRADO).estado_temporal, "cerrado")
        self.assertEqual(crear_cuestionario(estado=C.ARCHIVADO).estado_temporal, "archivado")


class AplicarAccionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()

    def test_publicar_exige_preguntas(self):
        vacio = crear_cuestionario(num_preguntas=0, estado=C.BORRADOR)
        with self.assertRaisesMessage(estados.CambioNoPermitido, "sin preguntas"):
            estados.aplicar_accion(vacio, "publicar")
        vacio.refresh_from_db()
        self.assertEqual(vacio.estado, C.BORRADOR)

    def test_publicar_rechaza_preguntas_inactivas(self):
        c = crear_cuestionario(estado=C.OCULTO)
        c.cuestionario_preguntas.first().pregunta.__class__.objects.filter(
            id=c.cuestionario_preguntas.first().pregunta_id,
        ).update(activa=False)
        with self.assertRaisesMessage(estados.CambioNoPermitido, "inactivas"):
            estados.aplicar_accion(c, "mostrar")

    def test_ciclo_completo(self):
        c = crear_cuestionario(estado=C.BORRADOR)
        for accion, esperado in [
            ("publicar", C.PUBLICADO), ("ocultar", C.OCULTO), ("mostrar", C.PUBLICADO),
            ("cerrar", C.CERRADO), ("reabrir", C.PUBLICADO), ("cerrar", C.CERRADO),
            ("archivar", C.ARCHIVADO), ("desarchivar", C.CERRADO),
        ]:
            with self.subTest(accion=accion):
                estados.aplicar_accion(c, accion)
                c.refresh_from_db()
                self.assertEqual(c.estado, esperado)

    def test_reabrir_con_fecha_vencida_pide_ampliarla(self):
        ahora = timezone.now()
        c = crear_cuestionario(
            estado=C.CERRADO, fecha_apertura=ahora - timedelta(days=3), fecha_cierre=ahora - timedelta(days=1),
        )
        with self.assertRaisesMessage(estados.CambioNoPermitido, "Amplíala"):
            estados.aplicar_accion(c, "reabrir")

    def test_no_archiva_un_cuestionario_abierto(self):
        c = crear_cuestionario()
        with self.assertRaises(estados.CambioNoPermitido):
            estados.aplicar_accion(c, "archivar")
        c.refresh_from_db()
        self.assertEqual(c.estado, C.PUBLICADO)

    def test_accion_desconocida(self):
        with self.assertRaises(estados.CambioNoPermitido):
            estados.aplicar_accion(crear_cuestionario(), "borrar")


class EstudianteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.estudiante = crear_usuario("est", "estudiante", codigo="E-1")

    def test_oculto_cerrado_y_archivado_no_aparecen_ni_se_inician(self):
        for estado in (C.OCULTO, C.CERRADO, C.ARCHIVADO):
            with self.subTest(estado=estado):
                c = crear_cuestionario(estado=estado)
                panel = panel_estudiante(self.estudiante)
                listados = [x.id for x in panel["cuestionarios_disponibles"]] + [x.id for x in panel["cuestionarios_programados"]]
                self.assertNotIn(c.id, listados)
                resultado = evaluacion.iniciar_intento(self.estudiante, c)
                self.assertEqual(resultado.tipo, "rechazado")
                self.assertIn("docente" if estado != C.ARCHIVADO else "archivada", resultado.mensaje)

    def test_quien_ya_presentaba_puede_retomar_tras_ocultar_o_cerrar(self):
        for accion in ("ocultar", "cerrar"):
            with self.subTest(accion=accion):
                c = crear_cuestionario()
                inicio = evaluacion.iniciar_intento(self.estudiante, c)
                self.assertEqual(inicio.tipo, "nuevo")
                estados.aplicar_accion(c, accion)
                c.refresh_from_db()
                retomado = evaluacion.iniciar_intento(self.estudiante, c)
                self.assertEqual(retomado.tipo, "reanudado")
                self.assertEqual(retomado.intento.id, inicio.intento.id)
                # El panel lo sigue mostrando con su intento en curso
                en_panel = {x.id: x for x in panel_estudiante(self.estudiante)["cuestionarios_disponibles"]}
                self.assertIn(c.id, en_panel)
                self.assertEqual(en_panel[c.id].intento_activo.id, inicio.intento.id)
                evaluacion.calificar_intento(retomado.intento, {})


class VistaCambiarEstadoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.admin = crear_usuario("adm", "admin")
        cls.docente = crear_usuario("prof", "docente")
        cls.estudiante = crear_usuario("est", "estudiante")

    def _url(self, c):
        return f"/cuestionarios/{c.id}/estado/"

    def test_admin_oculta_desde_el_listado(self):
        c = crear_cuestionario()
        self.client.force_login(self.admin)
        listado = self.client.get("/cuestionarios/")
        self.assertContains(listado, self._url(c))
        self.assertContains(listado, 'value="ocultar"')
        r = self.client.post(self._url(c), {"accion": "ocultar"})
        self.assertRedirects(r, "/cuestionarios/", fetch_redirect_response=False)
        c.refresh_from_db()
        self.assertEqual(c.estado, C.OCULTO)

    def test_accion_no_permitida_muestra_error_sin_cambiar(self):
        c = crear_cuestionario()
        self.client.force_login(self.admin)
        r = self.client.post(self._url(c), {"accion": "desarchivar"}, follow=True)
        self.assertContains(r, "No se puede desarchivar")
        c.refresh_from_db()
        self.assertEqual(c.estado, C.PUBLICADO)

    def test_solo_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self._url(crear_cuestionario())).status_code, 405)

    def test_docente_no_cambia_un_institucional_ajeno(self):
        c = crear_cuestionario()  # institucional, sin creador
        self.client.force_login(self.docente)
        self.assertEqual(self.client.post(self._url(c), {"accion": "ocultar"}).status_code, 403)
        c.refresh_from_db()
        self.assertEqual(c.estado, C.PUBLICADO)

    def test_estudiante_no_puede_cambiar_estados(self):
        c = crear_cuestionario()
        self.client.force_login(self.estudiante)
        self.assertNotEqual(self.client.post(self._url(c), {"accion": "cerrar"}).status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.estado, C.PUBLICADO)

    def test_guardar_en_el_editor_conserva_el_estado(self):
        c = crear_cuestionario(estado=C.OCULTO)
        self.client.force_login(self.admin)
        editor = self.client.get(f"/cuestionarios/{c.id}/editar/")
        self.assertContains(editor, 'value="guardar"')
        self.assertNotContains(editor, 'value="borrador"')
        ahora = timezone.localtime()
        self.client.post(f"/cuestionarios/{c.id}/editar/", {
            "accion": "guardar", "nombre": "Renombrado",
            "fecha_apertura": (ahora - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "fecha_cierre": (ahora + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "tiempo_limite_minutos": "60", "intentos_permitidos": "2",
            "calificacion_maxima": "5.00", "calificacion_aprobacion": "3.00",
            "visibilidad": "institucional",
            "preguntas_ids": [str(cp.pregunta_id) for cp in c.cuestionario_preguntas.all()],
        })
        c.refresh_from_db()
        self.assertEqual(c.nombre, "Renombrado")
        self.assertEqual(c.estado, C.OCULTO)
