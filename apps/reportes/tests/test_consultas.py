"""Módulo de consultas y reportes: filtros jerárquicos, indicadores, permisos y Excel."""
import io
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.academico.services import asignar_cursos_pendientes
from apps.banco_preguntas.models import Categoria
from apps.core.tests.factories import crear_cuestionario, crear_pregunta, crear_usuario, sembrar_roles
from apps.cuestionarios.models import CuestionarioPregunta
from apps.evaluaciones.models import Intento
from apps.evaluaciones.services import calificar_intento, iniciar_intento

URL = "/reportes/consultas/"


def presentar(estudiante, cuestionario, curso, correctas: int, cuando=None):
    """Intento terminado del estudiante con `correctas` respuestas acertadas (en orden)."""
    cuando = cuando or timezone.now()
    intento = Intento.objects.create(
        cuestionario=cuestionario, curso=curso, estado="en_progreso",
        participante_nombre=estudiante.get_full_name(), participante_codigo=estudiante.perfil.codigo_institucional,
    )
    Intento.objects.filter(id=intento.id).update(fecha_inicio=cuando)
    intento.refresh_from_db()
    respuestas = {}
    for i, cp in enumerate(cuestionario.cuestionario_preguntas.select_related("pregunta").order_by("orden")):
        opciones = cp.pregunta.opciones.order_by("orden")
        opcion = opciones.get(es_correcta=True) if i < correctas else opciones.filter(es_correcta=False).first()
        respuestas[str(cp.pregunta_id)] = opcion.id
    return calificar_intento(intento, respuestas, ahora=cuando + timedelta(minutes=5))


class BaseConsultas(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar_roles()
        cls.admin = crear_usuario("jefe", "admin", is_superuser=True, is_staff=True)
        cls.docente = crear_usuario("prof", "docente")
        cls.otro_docente = crear_usuario("otra", "docente")

        cls.p2025 = PeriodoAcademico.objects.create(anio=2025, numero=2, fecha_inicio=date(2025, 7, 1), fecha_fin=date(2025, 12, 15))
        cls.p2026 = PeriodoAcademico.objects.create(anio=2026, numero=2, fecha_inicio=date(2026, 7, 1), fecha_fin=date(2026, 12, 15))
        cls.sexto_a = Curso.objects.create(periodo=cls.p2026, asignatura="Frameworks", grupo="01", semestre=6, docente=cls.docente)
        cls.sexto_b = Curso.objects.create(periodo=cls.p2026, asignatura="Frameworks", grupo="02", semestre=6, docente=cls.otro_docente)
        cls.quinto = Curso.objects.create(periodo=cls.p2025, asignatura="Bases de Datos", grupo="01", semestre=5, docente=cls.docente)

        cls.ana = crear_usuario("ana", "estudiante", codigo="E1", first_name="Ana", last_name="Gómez")
        cls.beto = crear_usuario("beto", "estudiante", codigo="E2", first_name="Beto", last_name="Ruiz")
        cls.caro = crear_usuario("caro", "estudiante", codigo="E3", first_name="Caro", last_name="Paz")
        for est, curso in ((cls.ana, cls.sexto_a), (cls.beto, cls.sexto_a), (cls.caro, cls.sexto_b), (cls.ana, cls.quinto)):
            Matricula.objects.create(estudiante=est, curso=curso)

        # Simulacro con 4 preguntas: 2 de Lectura Crítica y 2 de Inglés
        cls.simulacro = crear_cuestionario(num_preguntas=0, nombre="Simulacro 1")
        cls.lectura = Categoria.objects.create(nombre="Lectura Crítica")
        cls.ingles = Categoria.objects.create(nombre="Inglés")
        for orden, cat in enumerate((cls.lectura, cls.lectura, cls.ingles, cls.ingles), start=1):
            p = crear_pregunta(cat, f"{cat.nombre} {orden}")
            CuestionarioPregunta.objects.create(cuestionario=cls.simulacro, pregunta=p, orden=orden, puntaje_asignado=p.puntaje)

        ahora = timezone.now()
        presentar(cls.ana, cls.simulacro, cls.sexto_a, 4, ahora - timedelta(days=2))   # 5,00
        presentar(cls.ana, cls.simulacro, cls.sexto_a, 2, ahora - timedelta(days=1))   # 2,50
        presentar(cls.beto, cls.simulacro, cls.sexto_a, 3, ahora)                      # 3,75
        presentar(cls.caro, cls.simulacro, cls.sexto_b, 1, ahora)                      # 1,25
        presentar(cls.ana, cls.simulacro, cls.quinto, 0, ahora - timedelta(days=300))  # 0,00
        Intento.objects.create(cuestionario=cls.simulacro, curso=cls.sexto_a, participante_codigo="E2",
                               participante_nombre="Beto Ruiz", estado="en_progreso")

    def consultar(self, usuario=None, **params):
        self.client.force_login(usuario or self.admin)
        return self.client.get(URL, params)

    def excel(self, reporte, usuario=None, **params):
        self.client.force_login(usuario or self.admin)
        return self.client.get(f"{URL}exportar/{reporte}/", params)


class IndicadoresTests(BaseConsultas):
    def test_consolidado_distingue_estudiantes_de_intentos(self):
        ind = self.consultar().context["indicadores"]
        self.assertEqual(ind["estudiantes"], 3)
        self.assertEqual(ind["intentos"], 5)      # el intento en progreso no cuenta
        self.assertEqual(ind["en_progreso"], 1)
        self.assertEqual(ind["promedio"], Decimal("2.50"))  # (5 + 2,5 + 3,75 + 1,25 + 0) / 5
        self.assertEqual((ind["minima"], ind["maxima"]), (Decimal("0.00"), Decimal("5.00")))
        self.assertEqual((ind["aprobados"], ind["no_aprobados"]), (2, 3))
        self.assertEqual(ind["porcentaje_aprobacion"], Decimal("40.0"))
        self.assertEqual(ind["umbrales"], [Decimal("3.00")])

    def test_filtrar_por_curso_cambia_indicadores(self):
        ind = self.consultar(curso=self.sexto_a.id).context["indicadores"]
        self.assertEqual((ind["estudiantes"], ind["intentos"]), (2, 3))
        self.assertEqual(ind["promedio"], Decimal("3.75"))

    def test_nota_se_expresa_sobre_cinco(self):
        sobre_diez = crear_cuestionario(num_preguntas=2, nombre="Escala 10",
                                        calificacion_maxima=Decimal("10.00"), calificacion_aprobacion=Decimal("6.00"))
        presentar(self.beto, sobre_diez, self.sexto_a, 1)  # 5/10 → 2,50 / 5
        r = self.consultar(estudiante="E2", q="Beto", curso=self.sexto_a.id, orden="nota")
        notas = [i.nota_5 for i in r.context["pagina"]]
        self.assertIn(Decimal("2.50"), notas)
        self.assertIn(Decimal("3.00"), r.context["indicadores"]["umbrales"])

    def test_sin_resultados(self):
        r = self.consultar(q="nadie")
        self.assertContains(r, "Sin resultados")
        self.assertEqual(r.context["indicadores"]["intentos"], 0)


class FiltrosTests(BaseConsultas):
    def test_periodo_incompatible_con_el_anio_se_limpia(self):
        r = self.consultar(anio=2025, periodo=self.p2026.id)
        self.assertIsNone(r.context["filtros"].periodo)
        self.assertEqual(r.context["filtros"].anio, 2025)
        self.assertEqual(r.context["indicadores"]["intentos"], 1)

    def test_curso_completa_periodo_y_anio(self):
        filtros = self.consultar(curso=self.sexto_b.id).context["filtros"]
        self.assertEqual((filtros.anio, filtros.periodo), (2026, self.p2026.id))

    def test_estudiante_fuera_del_curso_se_limpia(self):
        r = self.consultar(curso=self.sexto_b.id, estudiante="E1")
        self.assertEqual(r.context["filtros"].estudiante, "")
        self.assertEqual(r.context["indicadores"]["estudiantes"], 1)

    def test_eje_restringe_respuestas(self):
        r = self.consultar(eje=self.ingles.id, vista="ejes")
        self.assertEqual([f["eje"] for f in r.context["filas"]], ["Inglés"])
        fila = r.context["filas"][0]
        # Inglés = preguntas 3 y 4: aciertos 2 (Ana 4/4) + 0 + 1 (Beto 3/4) + 0 + 0
        self.assertEqual((fila["respondidas"], fila["aciertos"], fila["errores"]), (10, 3, 7))
        self.assertEqual(fila["porcentaje_aciertos"], Decimal("30.0"))

    def test_orden_y_paginacion_conservan_filtros(self):
        for _ in range(11):
            presentar(self.beto, self.simulacro, self.sexto_a, 2)
        r = self.consultar(curso=self.sexto_a.id, orden="nota")
        pagina = r.context["pagina"]
        self.assertEqual(len(pagina), 10)
        self.assertEqual(pagina[0].nota_5, Decimal("5.00"))
        self.assertContains(r, f"curso={self.sexto_a.id}")
        self.assertContains(r, "page=2")
        segunda = self.consultar(curso=self.sexto_a.id, orden="nota", page=2).context["pagina"]
        self.assertEqual(segunda.number, 2)

    def test_por_periodo_y_por_curso(self):
        periodos = {f["periodo"]: f for f in self.consultar(vista="periodos").context["filas"]}
        self.assertEqual(periodos["2026-2"]["intentos"], 4)
        self.assertEqual(periodos["2025-2"]["promedio"], Decimal("0.00"))
        cursos = {f["curso"]: f for f in self.consultar(vista="cursos").context["filas"]}
        self.assertEqual((cursos["Frameworks · G01"]["minima"], cursos["Frameworks · G01"]["maxima"]), (Decimal("2.50"), Decimal("5.00")))

    def test_historial_individual_en_orden_y_con_evolucion(self):
        historial = self.consultar(estudiante="E1", vista="historial").context["historial"]
        self.assertEqual([i.nota_5 for i in historial], [Decimal("0.00"), Decimal("5.00"), Decimal("2.50")])
        self.assertEqual(historial[2].cambio, Decimal("-2.50"))
        self.assertTrue(all(i.participante_codigo == "E1" for i in historial))
        self.assertEqual((historial[1].respondidas, historial[1].aciertos), (4, 4))

    def test_preguntas_mas_dificiles_primero(self):
        filas = self.consultar(vista="dificultad").context["pagina"].filas
        tasas = [f["porcentaje_aciertos"] for f in filas]
        self.assertEqual(tasas, sorted(tasas))
        self.assertEqual(filas[0]["eje"], "Inglés")


class PermisosTests(BaseConsultas):
    def test_requiere_sesion(self):
        self.assertEqual(self.client.get(URL).status_code, 302)
        self.assertEqual(self.client.get(f"{URL}exportar/consolidado/").status_code, 302)

    def test_estudiante_no_accede(self):
        self.assertEqual(self.consultar(self.ana).status_code, 403)
        self.assertEqual(self.excel("consolidado", self.ana).status_code, 403)

    def test_docente_solo_ve_sus_cursos(self):
        r = self.consultar(self.docente)
        self.assertEqual({c["nombre"] for c in r.context["catalogo"]["cursos"]}, {"Frameworks · G01", "Bases de Datos · G01"})
        self.assertEqual(r.context["indicadores"]["estudiantes"], 2)  # Ana y Beto, no Caro

    def test_docente_no_descarga_curso_ajeno_cambiando_la_url(self):
        self.assertEqual(self.consultar(self.docente, curso=self.sexto_b.id).status_code, 403)
        self.assertEqual(self.excel("consolidado", self.docente, curso=self.sexto_b.id).status_code, 403)

    def test_docente_no_ve_estudiante_ajeno(self):
        r = self.excel("historial", self.docente, estudiante="E3")
        libro = load_workbook(io.BytesIO(r.content))
        codigos = [fila[1].value for fila in libro.active.iter_rows(min_row=1) if fila[1].value == "E3"]
        self.assertEqual(codigos, [])


class ExcelTests(BaseConsultas):
    def _filas(self, respuesta, hoja=0):
        ws = load_workbook(io.BytesIO(respuesta.content)).worksheets[hoja]
        filas = list(ws.iter_rows(values_only=True))
        # La fila de encabezados de la tabla es la primera con 5 o más columnas llenas
        cabecera = next(i for i, f in enumerate(filas) if sum(v is not None for v in f) >= 5)
        return filas[:cabecera], filas[cabecera], [f for f in filas[cabecera + 1:] if any(v is not None for v in f)]

    def test_consolidado_exporta_todo_con_los_filtros(self):
        for _ in range(12):
            presentar(self.beto, self.simulacro, self.sexto_a, 2)
        r = self.excel("consolidado", curso=self.sexto_a.id)
        self.assertEqual(r.status_code, 200)
        self.assertIn("reporte_consolidado_2026-2_frameworks-g01", r["Content-Disposition"])
        encabezado, columnas, datos = self._filas(r)
        self.assertEqual(columnas[:9], ("Año", "Período", "Curso", "Estudiante", "Identificación", "Simulacro",
                                        "Fecha", "Calificación (/5,0)", "Estado"))
        self.assertEqual(len(datos), 16)  # todas, no solo la primera página de 10 (incluye la en progreso)
        texto = " ".join(str(v) for f in encabezado for v in f if v)
        self.assertIn("Frameworks · G01", texto)
        self.assertIn("Generado el", texto)

    def test_reporte_por_eje(self):
        _, columnas, datos = self._filas(self.excel("ejes"))
        self.assertIn("% de aciertos", columnas)
        self.assertEqual({(f[2], f[3]) for f in datos},
                         {("Frameworks · G01", "Inglés"), ("Frameworks · G01", "Lectura Crítica"), ("Frameworks · G02", "Inglés"),
                          ("Frameworks · G02", "Lectura Crítica"), ("Bases de Datos · G01", "Inglés"), ("Bases de Datos · G01", "Lectura Crítica")})

    def test_historial_cronologico(self):
        _, _, datos = self._filas(self.excel("historial", estudiante="E1"))
        self.assertEqual([f[9] for f in datos], [0, 5, 2.5])
        self.assertEqual([f[6] for f in datos], [4, 4, 4])  # respondidas

    def test_exportar_sin_registros_no_falla(self):
        for reporte in ("consolidado", "ejes", "historial"):
            r = self.excel(reporte, q="nadie")
            self.assertEqual(r.status_code, 200)
            _, _, datos = self._filas(r)
            self.assertEqual(datos[0][0], "Sin registros para los filtros aplicados.")

    def test_reporte_desconocido(self):
        self.assertEqual(self.excel("otro").status_code, 404)


class AsignacionCursoTests(BaseConsultas):
    def test_intento_nuevo_queda_en_el_curso_vigente(self):
        hoy = timezone.localdate()
        actual = PeriodoAcademico.objects.create(anio=2099, numero=1, fecha_inicio=hoy - timedelta(days=1), fecha_fin=hoy + timedelta(days=1))
        curso = Curso.objects.create(periodo=actual, asignatura="Vigente")
        Matricula.objects.create(estudiante=self.caro, curso=curso)
        resultado = iniciar_intento(self.caro, crear_cuestionario(num_preguntas=1, nombre="Hoy"))
        self.assertEqual(resultado.intento.curso, curso)

    def test_asignar_cursos_a_intentos_anteriores(self):
        intento = Intento.objects.create(cuestionario=self.simulacro, participante_codigo="E3",
                                         participante_nombre="Caro Paz", estado="finalizado")
        Intento.objects.filter(id=intento.id).update(fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 1, 10)))
        self.assertEqual(asignar_cursos_pendientes(), 1)
        intento.refresh_from_db()
        self.assertEqual(intento.curso, self.sexto_b)
