"""
Excel del módulo de consultas.

  consolidado  Reporte A: calificaciones, resumen, promedio por estudiante, por período y por curso
  ejes         Reporte B: desempeño por eje temático
  historial    Reporte C: historial individual
  dificultad   Preguntas de mayor dificultad

Cada libro reutiliza `intentos_filtrados` con los mismos filtros y alcance de
la pantalla y exporta TODOS los registros (no solo la página visible).

Diseño de cada hoja de datos (para que se lea y se pueda filtrar en Excel):
  fila 1  nombre del reporte
  fila 2  fecha de generación y solo los filtros aplicados
  fila 4  encabezados de la tabla (fijos al desplazarse y con autofiltro)
  fila 5… un registro por fila, una sola cosa por columna
La hoja «Acerca del reporte» detalla todos los filtros y las reglas de cálculo.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.reportes import consultas as c

AZUL = "18668F"
GRIS = "595957"
FMT_NOTA = "0.00"
FMT_PCT = "0.0%"
FMT_ENTERO = "0"
FMT_FECHA = "dd/mm/yyyy hh:mm"
FILA_TABLA = 4

REPORTES = {
    "consolidado": "Reporte A · Consolidado general",
    "ejes": "Reporte B · Desempeño por eje temático",
    "historial": "Reporte C · Historial individual",
    "dificultad": "Preguntas de mayor dificultad",
}
REGLAS_COMUNES = [
    "Las notas están sobre 5,0 (calificación × 5 / calificación máxima del simulacro).",
    "Promedios, mínimas, máximas y aprobación solo cuentan intentos terminados (finalizados o vencidos). "
    "Los intentos en progreso aparecen con estado «En progreso» y sin nota.",
    "Se aprueba con la nota mínima de cada simulacro.",
]
SIN_REGISTROS = "Sin registros para los filtros aplicados."


def _fecha_local(valor):
    # Excel no admite fechas con zona horaria
    return timezone.localtime(valor).replace(tzinfo=None) if valor else None


def _pct(valor):
    """El porcentaje se guarda como fracción para que Excel lo trate como porcentaje real."""
    return None if valor is None else Decimal(valor) / 100


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def nombre_archivo(reporte: str, filtros: c.Filtros) -> str:
    partes = [f"reporte_{reporte}"]
    for clave in ("periodo", "curso", "eje"):
        if clave in filtros.etiquetas:
            partes.append(_slug(filtros.etiquetas[clave]))
    if filtros.anio and "periodo" not in filtros.etiquetas:
        partes.append(str(filtros.anio))
    if filtros.estudiante:
        partes.append(_slug(filtros.estudiante))
    partes.append(timezone.localtime().strftime("%Y%m%d-%H%M"))
    return "_".join(partes) + ".xlsx"


# ---------------------------------------------------------------------------
# Escritura de hojas
# ---------------------------------------------------------------------------

@dataclass
class Col:
    titulo: str
    formato: str | None = None
    ancho_max: int = 40   # el ancho se ajusta al contenido hasta este límite
    envolver: bool = False  # textos largos (enunciados) en varias líneas


def _linea_filtros(filtros: c.Filtros) -> str:
    activos = filtros.activos
    texto = " · ".join(f"{n}: {v}" for n, v in activos) if activos else "sin filtros (todos los registros)"
    return f"Generado el {timezone.localtime().strftime('%d/%m/%Y %H:%M')} · Filtros: {texto}"


ESTILO_ESTADO = {
    "Aprobado": Font(bold=True, color="3B6B0E"),
    "No aprobado": Font(bold=True, color="A21F1F"),
    "En progreso": Font(italic=True, color=GRIS),
}


def hoja_tabla(ws, titulo: str, filtros: c.Filtros, columnas: list[Col], filas: list[list]):
    """Hoja con encabezado de dos líneas y una tabla limpia desde la fila 4."""
    ultima = get_column_letter(max(len(columnas), 6))
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=14, color=AZUL)
    ws["A2"] = _linea_filtros(filtros)
    ws["A2"].font = Font(italic=True, color=GRIS)
    for fila in (1, 2):  # el texto ocupa el ancho de la tabla, no solo la columna A
        ws.merge_cells(f"A{fila}:{ultima}{fila}")

    relleno = PatternFill("solid", fgColor=AZUL)
    franja = PatternFill("solid", fgColor="F2F6F8")
    borde = Border(bottom=Side(style="thin", color="D5D8DB"))
    for col, columna in enumerate(columnas, start=1):
        celda = ws.cell(row=FILA_TABLA, column=col, value=columna.titulo)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno
        celda.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[FILA_TABLA].height = 30

    if not filas:
        ws.cell(row=FILA_TABLA + 1, column=1, value=SIN_REGISTROS).font = Font(italic=True, color="A21F1F")
    for i, valores in enumerate(filas, start=1):
        for col, valor in enumerate(valores, start=1):
            columna = columnas[col - 1]
            celda = ws.cell(row=FILA_TABLA + i, column=col, value=valor)
            celda.border = borde
            if i % 2 == 0:
                celda.fill = franja
            if columna.formato and valor is not None and not isinstance(valor, str):
                celda.number_format = columna.formato
            if columna.envolver:
                celda.alignment = Alignment(wrap_text=True, vertical="top")
            if valor in ESTILO_ESTADO:
                celda.font = ESTILO_ESTADO[valor]

    # Ancho de cada columna según su contenido (con límite)
    for col, columna in enumerate(columnas, start=1):
        # El título se envuelve en dos líneas desde 14 caracteres; +3 deja sitio a la flecha del autofiltro
        largo = max([min(len(columna.titulo), 14) + 3] + [
            len(f"{v:.2f}" if isinstance(v, (Decimal, float)) else str(v)) for v in (f[col - 1] for f in filas)
            if v is not None
        ] + ([16] if columna.formato == FMT_FECHA else []))
        ws.column_dimensions[get_column_letter(col)].width = min(max(largo + 2, 8), columna.ancho_max)

    ws.freeze_panes = ws.cell(row=FILA_TABLA + 1, column=1)
    if filas:
        ws.auto_filter.ref = f"A{FILA_TABLA}:{get_column_letter(len(columnas))}{FILA_TABLA + len(filas)}"


def hoja_resumen(ws, titulo: str, filtros: c.Filtros, indicadores: list[tuple[str, object, str | None]]):
    """Indicadores en una tabla de dos columnas: nombre y valor (con su formato)."""
    hoja_tabla(ws, titulo, filtros, [Col("Indicador", ancho_max=44), Col("Valor", ancho_max=16)],
               [[nombre, valor] for nombre, valor, _ in indicadores])
    for i, (_, valor, formato) in enumerate(indicadores, start=FILA_TABLA + 1):
        if formato and valor is not None:
            ws.cell(row=i, column=2).number_format = formato
        ws.cell(row=i, column=2).alignment = Alignment(horizontal="right")
    ws.auto_filter.ref = None


def hoja_acerca(wb, titulo: str, filtros: c.Filtros, reglas: list[str]):
    """Detalle de todos los filtros y de cómo se calculan las cifras."""
    ws = wb.create_sheet("Acerca del reporte")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 95
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=14, color=AZUL)
    filas = [("Generado", timezone.localtime().strftime("%d/%m/%Y %H:%M")), ("", ""), ("Filtros aplicados", "")]
    filas += list(filtros.descripcion)
    filas += [("", ""), ("Cómo se calcula", "")] + [("", regla) for regla in reglas]
    for i, (a, b) in enumerate(filas, start=3):
        ws.cell(row=i, column=1, value=a or None)
        ws.cell(row=i, column=2, value=b or None).alignment = Alignment(wrap_text=True, vertical="top")
        if a in ("Filtros aplicados", "Cómo se calcula"):
            ws.cell(row=i, column=1).font = Font(bold=True, color=AZUL)
        elif a:
            ws.cell(row=i, column=1).font = Font(color=GRIS)


def _periodo_y_curso(intento) -> tuple:
    """(año, período, asignatura, grupo) del intento; el período no depende del curso."""
    asignatura, grupo = (intento.curso.asignatura, intento.curso.grupo) if intento.curso_id else ("Sin curso asignado", "")
    if intento.periodo_id:
        return intento.periodo.anio, intento.periodo.nombre, asignatura, grupo
    return None, "—", asignatura, grupo


# ---------------------------------------------------------------------------
# Libros
# ---------------------------------------------------------------------------

def libro_consolidado(filtros: c.Filtros, alcance: c.Alcance) -> Workbook:
    base = c.intentos_filtrados(filtros, alcance)
    wb = Workbook()
    titulo = REPORTES["consolidado"]

    filas = []
    for i in c.calificaciones(base, filtros.orden):
        anio, periodo, asignatura, grupo = _periodo_y_curso(i)
        filas.append([anio, periodo, asignatura, grupo, i.participante_nombre, i.participante_codigo,
                      i.cuestionario.nombre, _fecha_local(i.fecha_inicio), c._redondear(i.nota), c.estado_legible(i)])
    hoja_tabla(wb.active, titulo, filtros, [
        Col("Año", FMT_ENTERO), Col("Período"), Col("Asignatura", ancho_max=42), Col("Grupo"),
        Col("Estudiante", ancho_max=32), Col("Identificación"), Col("Simulacro", ancho_max=40),
        Col("Fecha", FMT_FECHA), Col("Nota (0 a 5)", FMT_NOTA), Col("Estado"),
    ], filas)
    wb.active.title = "Calificaciones"

    ind = c.indicadores(base)
    hoja_resumen(wb.create_sheet("Resumen"), "Resumen de la consulta", filtros, [
        ("Estudiantes evaluados (distintos)", ind["estudiantes"], FMT_ENTERO),
        ("Intentos terminados", ind["intentos"], FMT_ENTERO),
        ("Intentos en progreso (no cuentan)", ind["en_progreso"], FMT_ENTERO),
        ("Promedio (0 a 5)", ind["promedio"], FMT_NOTA),
        ("Nota mínima", ind["minima"], FMT_NOTA),
        ("Nota máxima", ind["maxima"], FMT_NOTA),
        ("Intentos aprobados", ind["aprobados"], FMT_ENTERO),
        ("Intentos no aprobados", ind["no_aprobados"], FMT_ENTERO),
        ("Porcentaje de aprobación", _pct(ind["porcentaje_aprobacion"]), FMT_PCT),
        ("Nota para aprobar (0 a 5)", ", ".join(f"{u:.2f}".replace(".", ",") for u in ind["umbrales"]) or "—", None),
    ])

    resumen = (
        c.terminados(base).values("participante_codigo")
        .annotate(nombre=c.Max("participante_nombre"), intentos=c.Count("id"), promedio=c.Avg("nota"), mejor=c.Max("nota"))
        .order_by("nombre")
    )
    hoja_tabla(wb.create_sheet("Por estudiante"), "Promedio por estudiante", filtros, [
        Col("Estudiante", ancho_max=32), Col("Identificación"), Col("Intentos terminados", FMT_ENTERO),
        Col("Promedio (0 a 5)", FMT_NOTA), Col("Mejor nota (0 a 5)", FMT_NOTA),
    ], [[r["nombre"], r["participante_codigo"], r["intentos"], c._redondear(r["promedio"]), c._redondear(r["mejor"])]
        for r in resumen])

    hoja_tabla(wb.create_sheet("Por período"), "Resultados por año y período", filtros, [
        Col("Período"), Col("Intentos terminados", FMT_ENTERO), Col("Estudiantes", FMT_ENTERO),
        Col("Promedio (0 a 5)", FMT_NOTA), Col("Aprobación", FMT_PCT),
    ], [[f["periodo"], f["intentos"], f["estudiantes"], f["promedio"], _pct(f["porcentaje_aprobacion"])]
        for f in c.por_periodo(base)])

    hoja_tabla(wb.create_sheet("Por curso"), "Resultados por curso", filtros, [
        Col("Asignatura", ancho_max=42), Col("Grupo"), Col("Período"), Col("Estudiantes", FMT_ENTERO),
        Col("Intentos", FMT_ENTERO), Col("Promedio (0 a 5)", FMT_NOTA), Col("Mínima", FMT_NOTA),
        Col("Máxima", FMT_NOTA), Col("Aprobación", FMT_PCT),
    ], [[f["asignatura"], f["grupo"], f["periodo"], f["estudiantes"], f["intentos"], f["promedio"], f["minima"],
         f["maxima"], _pct(f["porcentaje_aprobacion"])] for f in c.por_curso(base)])

    hoja_acerca(wb, titulo, filtros, REGLAS_COMUNES + [
        "«Estudiantes evaluados» cuenta personas distintas; un estudiante puede tener varios intentos.",
    ])
    return wb


def libro_ejes(filtros: c.Filtros, alcance: c.Alcance) -> Workbook:
    wb = Workbook()
    titulo = REPORTES["ejes"]
    filas = [[f["anio"] if f["anio"] != "—" else None, f["periodo"], f["asignatura"], f["grupo"], f["eje"],
              f["registradas"], f["aciertos"], f["errores"], f["omitidas"], _pct(f["porcentaje_aciertos"])]
             for f in c.por_eje(c.intentos_filtrados(filtros, alcance), filtros, detallar_curso=True)]
    hoja_tabla(wb.active, titulo, filtros, [
        Col("Año", FMT_ENTERO), Col("Período"), Col("Asignatura", ancho_max=42), Col("Grupo"),
        Col("Eje temático", ancho_max=30), Col("Respuestas registradas", FMT_ENTERO), Col("Aciertos", FMT_ENTERO),
        Col("Errores", FMT_ENTERO), Col("Sin responder", FMT_ENTERO), Col("% de aciertos", FMT_PCT),
    ], filas)
    wb.active.title = "Por eje"
    hoja_acerca(wb, titulo, filtros, [
        "Se calcula con las respuestas de intentos terminados.",
        "Respuestas registradas = aciertos + errores + sin responder.",
        "El porcentaje de aciertos es sobre las preguntas contestadas (aciertos + errores).",
        "No se incluye nota por eje: el sistema no tiene una regla para convertir los aciertos de un eje en calificación.",
    ])
    return wb


def libro_historial(filtros: c.Filtros, alcance: c.Alcance) -> Workbook:
    qs = c.con_conteos(c.intentos_filtrados(filtros, alcance), filtros).order_by(
        "participante_nombre", "participante_codigo", "fecha_inicio", "id",
    )
    wb = Workbook()
    titulo = REPORTES["historial"]
    filas = []
    for i in qs:
        _, periodo, asignatura, grupo = _periodo_y_curso(i)
        filas.append([i.participante_nombre, i.participante_codigo, asignatura, grupo, periodo, i.cuestionario.nombre,
                      _fecha_local(i.fecha_inicio), i.respondidas, i.aciertos, i.errores,
                      c._redondear(i.nota), c.estado_legible(i)])
    hoja_tabla(wb.active, titulo, filtros, [
        Col("Estudiante", ancho_max=32), Col("Identificación"), Col("Asignatura", ancho_max=42), Col("Grupo"),
        Col("Período"), Col("Simulacro", ancho_max=40), Col("Fecha", FMT_FECHA),
        Col("Preguntas respondidas", FMT_ENTERO), Col("Aciertos", FMT_ENTERO), Col("Errores", FMT_ENTERO),
        Col("Nota final (0 a 5)", FMT_NOTA), Col("Estado"),
    ], filas)
    wb.active.title = "Historial"
    hoja_acerca(wb, titulo, filtros, ["Un intento por fila, en orden cronológico dentro de cada estudiante."] + REGLAS_COMUNES)
    return wb


def libro_dificultad(filtros: c.Filtros, alcance: c.Alcance) -> Workbook:
    wb = Workbook()
    titulo = REPORTES["dificultad"]
    filas = [[f["id"], f["eje"], f["enunciado"], f["respondidas"], f["aciertos"], f["errores"], _pct(f["porcentaje_aciertos"])]
             for f in map(c.fila_dificultad, c.dificultad(c.intentos_filtrados(filtros, alcance), filtros))]
    hoja_tabla(wb.active, titulo, filtros, [
        Col("N.º", FMT_ENTERO), Col("Eje temático", ancho_max=30), Col("Pregunta", ancho_max=70, envolver=True),
        Col("Respuestas", FMT_ENTERO), Col("Aciertos", FMT_ENTERO), Col("Errores", FMT_ENTERO), Col("% de acierto", FMT_PCT),
    ], filas)
    wb.active.title = "Preguntas difíciles"
    hoja_acerca(wb, titulo, filtros, [
        "De menor a mayor porcentaje de acierto, sobre las respuestas contestadas en intentos terminados.",
        "Las preguntas sin respuestas en los intentos filtrados no aparecen.",
    ])
    return wb


LIBROS = {"consolidado": libro_consolidado, "ejes": libro_ejes, "historial": libro_historial,
          "dificultad": libro_dificultad}
