"""
Excel del módulo de consultas: A (consolidado), B (por eje) y C (historial).

Cada libro reutiliza `intentos_filtrados` con los mismos filtros y alcance de
la pantalla, exporta TODOS los registros (no solo la página visible) e
incluye un encabezado con el nombre del reporte, la fecha de generación, los
filtros activos y las reglas de cálculo.
"""
from __future__ import annotations

import re
import unicodedata

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.reportes import consultas as c

AZUL = "18668F"
FMT_NOTA = "0.00"
FMT_PCT = '0.0"%"'
FMT_FECHA = "dd/mm/yyyy hh:mm"

REPORTES = {
    "consolidado": "Reporte A · Consolidado general",
    "ejes": "Reporte B · Desempeño por eje temático",
    "historial": "Reporte C · Historial individual",
}


def _fecha_local(valor):
    # Excel no admite fechas con zona horaria
    return timezone.localtime(valor).replace(tzinfo=None) if valor else None


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


def _encabezado(ws, titulo: str, filtros: c.Filtros, notas: list[str]) -> int:
    """Escribe el bloque de encabezado y retorna la fila donde empieza la tabla."""
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=14, color=AZUL)
    ws["A2"] = f"Generado el {timezone.localtime().strftime('%d/%m/%Y %H:%M')}"
    ws["A2"].font = Font(italic=True, color="595957")
    fila = 4
    ws.cell(row=fila, column=1, value="Filtros aplicados").font = Font(bold=True)
    for nombre, valor in filtros.descripcion:
        fila += 1
        ws.cell(row=fila, column=1, value=nombre).font = Font(color="595957")
        ws.cell(row=fila, column=2, value=valor)
    for nota in notas:
        fila += 1
        ws.cell(row=fila, column=1, value=nota).font = Font(italic=True, color="595957")
    return fila + 2


def _tabla(ws, fila_inicio: int, columnas: list[tuple[str, int, str | None]], filas: list[list], vacio: str):
    """columnas: (encabezado, ancho, formato)."""
    relleno = PatternFill("solid", fgColor=AZUL)
    borde = Border(bottom=Side(style="thin", color="D5D8DB"))
    for col, (titulo, ancho, _) in enumerate(columnas, start=1):
        celda = ws.cell(row=fila_inicio, column=col, value=titulo)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno
        celda.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = ancho
    if not filas:
        ws.cell(row=fila_inicio + 1, column=1, value=vacio).font = Font(italic=True, color="A21F1F")
    for i, valores in enumerate(filas, start=1):
        for col, valor in enumerate(valores, start=1):
            celda = ws.cell(row=fila_inicio + i, column=col, value=valor)
            celda.border = borde
            formato = columnas[col - 1][2]
            if formato and valor is not None and not isinstance(valor, str):
                celda.number_format = formato
    ws.freeze_panes = ws.cell(row=fila_inicio + 1, column=1)
    if filas:
        ws.auto_filter.ref = f"A{fila_inicio}:{get_column_letter(len(columnas))}{fila_inicio + len(filas)}"


NOTA_ESCALA = "Notas sobre 5,0. Promedios, mínimos y máximos solo con intentos terminados (finalizados o vencidos)."
VACIO = "Sin registros para los filtros aplicados."


def _periodo(intento) -> tuple:
    if intento.curso_id:
        return intento.curso.periodo.anio, intento.curso.periodo.nombre, intento.curso.nombre
    return "—", "—", "Sin curso asignado"


def libro_consolidado(filtros: c.Filtros, alcance: c.Alcance) -> Workbook:
    qs = c.calificaciones(c.intentos_filtrados(filtros, alcance), filtros.orden)
    ind = c.indicadores(c.intentos_filtrados(filtros, alcance))
    wb = Workbook()
    ws = wb.active
    ws.title = "Calificaciones"
    umbral = ", ".join(f"{u:.2f}" for u in ind["umbrales"]) or "—"
    inicio = _encabezado(ws, REPORTES["consolidado"], filtros, [
        NOTA_ESCALA, f"Nota mínima de aprobación (sobre 5,0): {umbral}.",
        f"Estudiantes distintos: {ind['estudiantes']} · Intentos terminados: {ind['intentos']} · "
        f"Promedio: {ind['promedio'] if ind['promedio'] is not None else '—'} · "
        f"Aprobados: {ind['aprobados']} · No aprobados: {ind['no_aprobados']}",
    ])
    filas = []
    for i in qs:
        anio, periodo, curso = _periodo(i)
        filas.append([anio, periodo, curso, i.participante_nombre, i.participante_codigo, i.cuestionario.nombre,
                      _fecha_local(i.fecha_inicio), c._redondear(i.nota), c.estado_legible(i)])
    _tabla(ws, inicio, [
        ("Año", 8, None), ("Período", 10, None), ("Curso", 18, None), ("Estudiante", 28, None),
        ("Identificación", 16, None), ("Simulacro", 30, None), ("Fecha", 17, FMT_FECHA),
        ("Calificación (/5,0)", 14, FMT_NOTA), ("Estado", 14, None),
    ], filas, VACIO)

    # Hoja 2: promedio por estudiante
    ws2 = wb.create_sheet("Promedio por estudiante")
    inicio = _encabezado(ws2, "Promedio por estudiante", filtros, [NOTA_ESCALA])
    resumen = (
        c.terminados(c.intentos_filtrados(filtros, alcance))
        .values("participante_codigo")
        .annotate(nombre=c.Max("participante_nombre"), intentos=c.Count("id"),
                  promedio=c.Avg("nota"), mejor=c.Max("nota"))
        .order_by("nombre")
    )
    _tabla(ws2, inicio, [
        ("Estudiante", 28, None), ("Identificación", 16, None), ("Intentos terminados", 12, "0"),
        ("Promedio (/5,0)", 14, FMT_NOTA), ("Mejor nota (/5,0)", 14, FMT_NOTA),
    ], [[r["nombre"], r["participante_codigo"], r["intentos"], c._redondear(r["promedio"]), c._redondear(r["mejor"])]
        for r in resumen], VACIO)
    return wb


def libro_ejes(filtros: c.Filtros, alcance: c.Alcance) -> Workbook:
    qs = c.intentos_filtrados(filtros, alcance)
    wb = Workbook()
    ws = wb.active
    ws.title = "Desempeño por eje"
    inicio = _encabezado(ws, REPORTES["ejes"], filtros, [
        "Calculado con las respuestas de intentos terminados. Porcentaje de aciertos sobre respuestas contestadas.",
        "Nota promedio por eje: no definida (el sistema no tiene una regla para convertir aciertos de un eje en nota).",
    ])
    filas = [[f["anio"], f["periodo"], f["curso"], f["eje"], f["registradas"], f["respondidas"], f["aciertos"],
              f["errores"], f["omitidas"], f["porcentaje_aciertos"], "No definida"]
             for f in c.por_eje(qs, filtros, detallar_curso=True)]
    _tabla(ws, inicio, [
        ("Año", 8, None), ("Período", 10, None), ("Curso", 18, None), ("Eje temático", 28, None),
        ("Respuestas registradas", 12, "0"), ("Contestadas", 12, "0"), ("Aciertos", 10, "0"), ("Errores", 10, "0"),
        ("Sin responder", 12, "0"), ("% de aciertos", 12, FMT_PCT), ("Nota promedio", 14, None),
    ], filas, VACIO)
    return wb


def libro_historial(filtros: c.Filtros, alcance: c.Alcance) -> Workbook:
    qs = c.con_conteos(c.intentos_filtrados(filtros, alcance), filtros).order_by(
        "participante_nombre", "participante_codigo", "fecha_inicio", "id",
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "Historial"
    inicio = _encabezado(ws, REPORTES["historial"], filtros, [
        "Un intento por fila, en orden cronológico por estudiante. " + NOTA_ESCALA,
    ])
    filas = []
    for i in qs:
        _, periodo, curso = _periodo(i)
        filas.append([i.participante_nombre, i.participante_codigo, curso, periodo, i.cuestionario.nombre,
                      _fecha_local(i.fecha_inicio), i.respondidas, i.aciertos, i.errores,
                      c._redondear(i.nota), c.estado_legible(i)])
    _tabla(ws, inicio, [
        ("Estudiante", 28, None), ("Identificación", 16, None), ("Curso", 18, None), ("Período", 10, None),
        ("Simulacro", 30, None), ("Fecha", 17, FMT_FECHA), ("Preguntas respondidas", 12, "0"),
        ("Aciertos", 10, "0"), ("Errores", 10, "0"), ("Nota final (/5,0)", 14, FMT_NOTA), ("Estado", 14, None),
    ], filas, VACIO)
    return wb


LIBROS = {"consolidado": libro_consolidado, "ejes": libro_ejes, "historial": libro_historial}
