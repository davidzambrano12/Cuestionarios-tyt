"""
Módulo de consultas y reportes (guía «Módulo de consultas, reportes y
exportación a Excel»).

Filtros jerárquicos: AÑO → PERÍODO → CURSO → EJE TEMÁTICO → ESTUDIANTE.
Toda la información sale de la base de datos con el ORM; la misma función
`intentos_filtrados` alimenta la pantalla y los Excel, así lo descargado
coincide con lo consultado.

Reglas de cálculo:
  * Las notas se expresan sobre 5,0: nota = calificación × 5 / calificación máxima
    del simulacro (en la práctica la mayoría ya usa 5,0).
  * Solo los intentos terminados (finalizados o vencidos, con nota) cuentan para
    promedios, mínimos, máximos y aprobación. Los que siguen en progreso se
    muestran pero se excluyen de esas cifras.
  * Aprobación: la regla de cada simulacro (`calificacion_aprobacion`), que
    se guarda en `intentos.aprobado` al calificar.
  * Desempeño por eje: se calcula con las respuestas efectivamente
    contestadas. No se calcula una nota por eje porque el sistema no define
    una regla para convertir aciertos en calificación.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.db.models import (
    Avg, Count, DecimalField, ExpressionWrapper, F, Max, Min, OuterRef, Q, Subquery, Value,
)
from django.db.models.functions import Coalesce

from apps.academico.models import Curso, Matricula, PeriodoAcademico
from apps.banco_preguntas.models import Categoria
from apps.core.services.acceso import codigo_participante, perfil_de
from apps.evaluaciones.models import Intento, RespuestaIntento

ESCALA = Decimal("5.00")
POR_PAGINA = 10
TERMINADOS = ("finalizado", "vencido")
VISTAS = ("calificaciones", "periodos", "cursos", "ejes", "historial", "dificultad")
ORDENES = {
    "fecha": ("-fecha_inicio",),
    "nombre": ("participante_nombre", "-fecha_inicio"),
    "nota": (F("nota").desc(nulls_last=True), "-fecha_inicio"),
}
DECIMAL = DecimalField(max_digits=7, decimal_places=4)


# ---------------------------------------------------------------------------
# Alcance según el rol
# ---------------------------------------------------------------------------

@dataclass
class Alcance:
    """Qué cursos (e intentos) puede consultar el usuario."""
    es_admin: bool
    cursos: object  # QuerySet[Curso]

    def intentos(self):
        base = Intento.objects.all()
        if self.es_admin:
            return base
        # Un docente solo ve los intentos de los cursos que tiene a cargo
        return base.filter(curso__in=self.cursos)


def alcance_de(user) -> Alcance:
    perfil = perfil_de(user)
    es_admin = bool(user.is_superuser or (perfil and perfil.es_admin))
    cursos = Curso.objects.select_related("periodo")
    if not es_admin:
        cursos = cursos.filter(docente=user)
    return Alcance(es_admin=es_admin, cursos=cursos)


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

def _entero(valor):
    try:
        return int(valor) if valor not in (None, "") else None
    except (TypeError, ValueError):
        return None


@dataclass
class Filtros:
    anio: int | None = None
    periodo: int | None = None
    curso: int | None = None
    eje: int | None = None
    estudiante: str = ""
    q: str = ""
    orden: str = "fecha"
    vista: str = "calificaciones"
    avisos: list[str] = field(default_factory=list)
    # Nombres legibles de lo seleccionado, para la pantalla y los Excel
    etiquetas: dict = field(default_factory=dict)

    def params(self, **cambios) -> dict:
        datos = {
            "anio": self.anio, "periodo": self.periodo, "curso": self.curso, "eje": self.eje,
            "estudiante": self.estudiante, "q": self.q, "orden": self.orden, "vista": self.vista,
        }
        datos.update(cambios)
        return {k: v for k, v in datos.items() if v not in (None, "")}

    def querystring(self, **cambios) -> str:
        return urlencode(self.params(**cambios))

    @property
    def descripcion(self) -> list[tuple[str, str]]:
        """Filtros activos como pares (filtro, valor); «Todos» si no se eligió."""
        e = self.etiquetas
        return [
            ("Año", str(self.anio) if self.anio else "Todos"),
            ("Período", e.get("periodo", "Todos")),
            ("Curso", e.get("curso", "Todos")),
            ("Eje temático", e.get("eje", "Todos")),
            ("Estudiante", e.get("estudiante", "Todos")),
            ("Búsqueda", self.q or "—"),
        ]

    @property
    def hay_filtros(self) -> bool:
        return any([self.anio, self.periodo, self.curso, self.eje, self.estudiante, self.q])


def catalogo(alcance: Alcance) -> dict:
    """Opciones de cada filtro dentro del alcance (base de los filtros dependientes)."""
    cursos = list(alcance.cursos.order_by("-periodo__anio", "-periodo__numero", "nombre"))
    periodos_ids = {c.periodo_id for c in cursos}
    periodos = PeriodoAcademico.objects.all() if alcance.es_admin else PeriodoAcademico.objects.filter(id__in=periodos_ids)
    periodos = list(periodos.order_by("-anio", "-numero"))

    estudiantes = {}
    matriculas = (
        Matricula.objects.filter(curso__in=[c.id for c in cursos])
        .select_related("estudiante__perfil", "curso")
        .order_by("estudiante__first_name", "estudiante__last_name")
    )
    for m in matriculas:
        codigo = codigo_participante(m.estudiante)
        item = estudiantes.setdefault(codigo, {
            "codigo": codigo,
            "nombre": m.estudiante.get_full_name() or m.estudiante.username,
            "cursos": [], "periodos": [], "anios": [],
        })
        item["cursos"].append(m.curso_id)
        item["periodos"].append(m.curso.periodo_id)
    anio_de = {p.id: p.anio for p in periodos}
    for item in estudiantes.values():
        item["anios"] = sorted({anio_de[p] for p in item["periodos"] if p in anio_de})

    return {
        "anios": sorted({p.anio for p in periodos}, reverse=True),
        "periodos": [{"id": p.id, "anio": p.anio, "nombre": p.nombre} for p in periodos],
        "cursos": [{"id": c.id, "periodo": c.periodo_id, "nombre": c.nombre} for c in cursos],
        "ejes": [{"id": c.id, "nombre": c.nombre} for c in Categoria.objects.order_by("nombre")],
        "estudiantes": sorted(estudiantes.values(), key=lambda e: e["nombre"].lower()),
    }


def leer_filtros(datos, alcance: Alcance, cat: dict | None = None) -> Filtros:
    """
    Lee los filtros de la URL. Un valor fuera del alcance del usuario (un
    curso o período que no le corresponde) es un intento de acceso indebido y
    se rechaza con PermissionDenied. Un valor dentro del alcance pero
    incompatible con el filtro padre se limpia y se avisa.
    """
    cat = cat or catalogo(alcance)
    f = Filtros(
        anio=_entero(datos.get("anio")),
        periodo=_entero(datos.get("periodo")),
        curso=_entero(datos.get("curso")),
        eje=_entero(datos.get("eje")),
        estudiante=(datos.get("estudiante") or "").strip()[:50],
        q=(datos.get("q") or "").strip()[:100],
        orden=datos.get("orden") if datos.get("orden") in ORDENES else "fecha",
        vista=datos.get("vista") if datos.get("vista") in VISTAS else "calificaciones",
    )
    periodos = {p["id"]: p for p in cat["periodos"]}
    cursos = {c["id"]: c for c in cat["cursos"]}
    ejes = {e["id"]: e for e in cat["ejes"]}
    estudiantes = {e["codigo"]: e for e in cat["estudiantes"]}

    # Fuera del alcance: rechazo explícito (p. ej. un curso de otro docente en la URL)
    if f.periodo and f.periodo not in periodos and PeriodoAcademico.objects.filter(id=f.periodo).exists():
        raise PermissionDenied("No tienes acceso a ese período.")
    if f.curso and f.curso not in cursos and Curso.objects.filter(id=f.curso).exists():
        raise PermissionDenied("No tienes acceso a ese curso.")

    # Valores inexistentes o incompatibles con el filtro padre: se limpian
    if f.anio and f.anio not in cat["anios"]:
        f.avisos.append(f"No hay períodos registrados para el año {f.anio}.")
        f.anio = None
    if f.periodo and (f.periodo not in periodos or (f.anio and periodos[f.periodo]["anio"] != f.anio)):
        f.avisos.append("El período elegido no corresponde al año; se quitó ese filtro.")
        f.periodo = None
    if f.periodo and not f.anio:
        f.anio = periodos[f.periodo]["anio"]
    if f.curso and (f.curso not in cursos or (f.periodo and cursos[f.curso]["periodo"] != f.periodo)
                    or (f.anio and periodos.get(cursos[f.curso]["periodo"], {}).get("anio") != f.anio)):
        f.avisos.append("El curso elegido no pertenece al período; se quitó ese filtro.")
        f.curso = None
    if f.curso and not f.periodo:
        f.periodo = cursos[f.curso]["periodo"]
        f.anio = periodos[f.periodo]["anio"]
    if f.eje and f.eje not in ejes:
        f.eje = None
    if f.estudiante:
        est = estudiantes.get(f.estudiante)
        compatible = est and (
            (not f.curso or f.curso in est["cursos"])
            and (not f.periodo or f.periodo in est["periodos"])
            and (not f.anio or f.anio in est["anios"])
        )
        if not compatible and not (alcance.es_admin and not est and _hay_intentos_de(f.estudiante)):
            f.avisos.append("El estudiante elegido no pertenece al curso o período seleccionado; se quitó ese filtro.")
            f.estudiante = ""

    if f.periodo:
        f.etiquetas["periodo"] = periodos[f.periodo]["nombre"]
    if f.curso:
        f.etiquetas["curso"] = cursos[f.curso]["nombre"]
    if f.eje:
        f.etiquetas["eje"] = ejes[f.eje]["nombre"]
    if f.estudiante:
        est = estudiantes.get(f.estudiante)
        nombre = est["nombre"] if est else _nombre_participante(f.estudiante)
        f.etiquetas["estudiante"] = f"{nombre} ({f.estudiante})"
    return f


def _hay_intentos_de(codigo: str) -> bool:
    return Intento.objects.filter(participante_codigo=codigo).exists()


def _nombre_participante(codigo: str) -> str:
    return (
        Intento.objects.filter(participante_codigo=codigo).order_by("-fecha_inicio")
        .values_list("participante_nombre", flat=True).first() or codigo
    )


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def _nota_sobre_5():
    return ExpressionWrapper(
        F("calificacion") * ESCALA / F("cuestionario__calificacion_maxima"), output_field=DECIMAL,
    )


def intentos_filtrados(filtros: Filtros, alcance: Alcance):
    """Intentos que cumplen los filtros (todos los estados), con la nota sobre 5,0."""
    qs = alcance.intentos().select_related("cuestionario", "curso__periodo")
    if filtros.anio:
        qs = qs.filter(curso__periodo__anio=filtros.anio)
    if filtros.periodo:
        qs = qs.filter(curso__periodo_id=filtros.periodo)
    if filtros.curso:
        qs = qs.filter(curso_id=filtros.curso)
    if filtros.eje:
        # Simulacros que incluyen preguntas de ese eje
        qs = qs.filter(id__in=RespuestaIntento.objects.filter(pregunta__categoria_id=filtros.eje).values("intento_id"))
    if filtros.estudiante:
        qs = qs.filter(participante_codigo=filtros.estudiante)
    if filtros.q:
        qs = qs.filter(Q(participante_nombre__icontains=filtros.q) | Q(participante_codigo__icontains=filtros.q))
    return qs.annotate(nota=_nota_sobre_5())


def terminados(qs):
    return qs.filter(estado__in=TERMINADOS, calificacion__isnull=False)


def _porcentaje(parte, total) -> Decimal | None:
    if not total:
        return None
    return (Decimal(parte) * 100 / Decimal(total)).quantize(Decimal("0.1"))


def _redondear(valor) -> Decimal | None:
    return Decimal(valor).quantize(Decimal("0.01")) if valor is not None else None


def indicadores(qs) -> dict:
    """Consulta 1: consolidado general."""
    hechos = terminados(qs)
    agregado = hechos.aggregate(
        intentos=Count("id"),
        estudiantes=Count("participante_codigo", distinct=True),
        promedio=Avg("nota"), minima=Min("nota"), maxima=Max("nota"),
        aprobados=Count("id", filter=Q(aprobado=True)),
    )
    umbrales = sorted({
        _redondear(a * ESCALA / m)
        for a, m in hechos.values_list("cuestionario__calificacion_aprobacion", "cuestionario__calificacion_maxima").distinct()
    })
    return {
        "estudiantes": agregado["estudiantes"],
        "intentos": agregado["intentos"],
        "en_progreso": qs.filter(estado="en_progreso").count(),
        "promedio": _redondear(agregado["promedio"]),
        "minima": _redondear(agregado["minima"]),
        "maxima": _redondear(agregado["maxima"]),
        "aprobados": agregado["aprobados"],
        "no_aprobados": agregado["intentos"] - agregado["aprobados"],
        "porcentaje_aprobacion": _porcentaje(agregado["aprobados"], agregado["intentos"]),
        "umbrales": umbrales,
    }


def calificaciones(qs, orden: str):
    """Consulta 5: un intento por fila, ordenable."""
    return qs.order_by(*ORDENES.get(orden, ORDENES["fecha"]))


def por_periodo(qs) -> list[dict]:
    """Consulta 2: evaluaciones y promedio por año y período."""
    filas = (
        terminados(qs)
        .values("curso__periodo__anio", "curso__periodo__numero")
        .annotate(
            intentos=Count("id"), estudiantes=Count("participante_codigo", distinct=True),
            promedio=Avg("nota"), aprobados=Count("id", filter=Q(aprobado=True)),
        )
        .order_by("-curso__periodo__anio", "-curso__periodo__numero")
    )
    return [{
        "anio": f["curso__periodo__anio"],
        "periodo": f"{f['curso__periodo__anio']}-{f['curso__periodo__numero']}" if f["curso__periodo__anio"] else "Sin curso asignado",
        "intentos": f["intentos"], "estudiantes": f["estudiantes"],
        "promedio": _redondear(f["promedio"]),
        "porcentaje_aprobacion": _porcentaje(f["aprobados"], f["intentos"]),
    } for f in filas]


def por_curso(qs) -> list[dict]:
    """Consulta 3: estudiantes, promedio, mínima y máxima por curso."""
    filas = (
        terminados(qs)
        .values("curso_id", "curso__nombre", "curso__periodo__anio", "curso__periodo__numero")
        .annotate(
            intentos=Count("id"), estudiantes=Count("participante_codigo", distinct=True),
            promedio=Avg("nota"), minima=Min("nota"), maxima=Max("nota"),
            aprobados=Count("id", filter=Q(aprobado=True)),
        )
        .order_by("-curso__periodo__anio", "-curso__periodo__numero", "curso__nombre")
    )
    return [{
        "curso_id": f["curso_id"],
        "curso": f["curso__nombre"] or "Sin curso asignado",
        "periodo": f"{f['curso__periodo__anio']}-{f['curso__periodo__numero']}" if f["curso__periodo__anio"] else "—",
        "anio": f["curso__periodo__anio"],
        "intentos": f["intentos"], "estudiantes": f["estudiantes"],
        "promedio": _redondear(f["promedio"]), "minima": _redondear(f["minima"]), "maxima": _redondear(f["maxima"]),
        "porcentaje_aprobacion": _porcentaje(f["aprobados"], f["intentos"]),
    } for f in filas]


def _respuestas(qs, filtros: Filtros):
    respuestas = RespuestaIntento.objects.filter(intento__in=terminados(qs).values("id"))
    if filtros.eje:
        respuestas = respuestas.filter(pregunta__categoria_id=filtros.eje)
    return respuestas


def _metricas_respuesta(fila: dict) -> dict:
    respondidas = fila["respondidas"]
    fila["errores"] = respondidas - fila["aciertos"]
    fila["omitidas"] = fila["registradas"] - respondidas
    fila["porcentaje_aciertos"] = _porcentaje(fila["aciertos"], respondidas)
    return fila


_CONTEO_RESPUESTAS = {
    "registradas": Count("id"),
    "respondidas": Count("id", filter=Q(opcion_seleccionada__isnull=False)),
    "aciertos": Count("id", filter=Q(es_correcta=True)),
}


def por_eje(qs, filtros: Filtros, *, detallar_curso: bool = False) -> list[dict]:
    """Consulta 4 (y Reporte B si `detallar_curso`): aciertos por eje temático."""
    campos = ["pregunta__categoria__nombre"]
    if detallar_curso:
        campos = ["intento__curso__periodo__anio", "intento__curso__periodo__numero", "intento__curso__nombre", *campos]
    filas = _respuestas(qs, filtros).values(*campos).annotate(**_CONTEO_RESPUESTAS).order_by(*[
        f"-{c}" if "periodo" in c else c for c in campos
    ])
    resultado = []
    for f in filas:
        fila = _metricas_respuesta({
            "eje": f["pregunta__categoria__nombre"],
            "registradas": f["registradas"], "respondidas": f["respondidas"], "aciertos": f["aciertos"],
        })
        if detallar_curso:
            anio = f["intento__curso__periodo__anio"]
            fila.update(
                anio=anio or "—",
                periodo=f"{anio}-{f['intento__curso__periodo__numero']}" if anio else "—",
                curso=f["intento__curso__nombre"] or "Sin curso asignado",
            )
        resultado.append(fila)
    return resultado


def dificultad(qs, filtros: Filtros):
    """Consulta 7: preguntas con menor porcentaje de acierto (respuestas contestadas)."""
    filas = (
        _respuestas(qs, filtros).filter(opcion_seleccionada__isnull=False)
        .values("pregunta_id", "pregunta__enunciado", "pregunta__categoria__nombre")
        .annotate(respondidas=Count("id"), aciertos=Count("id", filter=Q(es_correcta=True)))
        .annotate(
            tasa=ExpressionWrapper(F("aciertos") * Value(Decimal("1.0")) / F("respondidas"), output_field=DECIMAL),
        )
        .order_by("tasa", "-respondidas", "pregunta_id")
    )
    return filas


def fila_dificultad(f: dict) -> dict:
    return {
        "id": f["pregunta_id"], "enunciado": f["pregunta__enunciado"], "eje": f["pregunta__categoria__nombre"],
        "respondidas": f["respondidas"], "aciertos": f["aciertos"], "errores": f["respondidas"] - f["aciertos"],
        "porcentaje_aciertos": _porcentaje(f["aciertos"], f["respondidas"]),
    }


def con_conteos(qs, filtros: Filtros):
    """Añade respondidas, aciertos y errores por intento (subconsultas: no multiplican filas)."""
    base = RespuestaIntento.objects.filter(intento=OuterRef("pk"))
    if filtros.eje:
        base = base.filter(pregunta__categoria_id=filtros.eje)

    def contar(**condicion):
        sub = base.filter(**condicion).order_by().values("intento").annotate(n=Count("id")).values("n")
        return Coalesce(Subquery(sub), 0)

    return qs.annotate(
        respondidas=contar(opcion_seleccionada__isnull=False),
        aciertos=contar(es_correcta=True),
    ).annotate(errores=F("respondidas") - F("aciertos"))


def historial(qs, filtros: Filtros) -> list:
    """Consulta 6: intentos del estudiante en orden cronológico, con la evolución de la nota."""
    intentos = list(con_conteos(qs, filtros).order_by("fecha_inicio", "id"))
    anterior = None
    for intento in intentos:
        intento.nota_5 = _redondear(intento.nota)
        intento.cambio = None
        if intento.nota_5 is not None:
            if anterior is not None:
                intento.cambio = intento.nota_5 - anterior
            anterior = intento.nota_5
    return intentos


def estado_legible(intento) -> str:
    if intento.estado == "en_progreso":
        return "En progreso"
    if intento.calificacion is None:
        return "Sin nota"
    return "Aprobado" if intento.aprobado else "No aprobado"
