"""
Reportes de calificaciones (CU-05): agrupación por estudiante con nota
definitiva, métricas del grupo y exportación a Excel.
"""
from collections import OrderedDict
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.banco_preguntas.models import Categoria, Pregunta
from apps.cuestionarios.models import Cuestionario
from apps.evaluaciones.models import Intento
from apps.evaluaciones.services import dictamen_intento, intento_calificado

def resumen_por_estudiante(cuestionario, intentos):
    """
    Agrupa los intentos por estudiante (código) y calcula la nota definitiva
    institucional (la calificación más alta entre intentos cerrados).
    Retorna (estudiantes, metricas).
    """
    estudiantes = OrderedDict()
    for it in intentos:
        datos = estudiantes.setdefault(it.participante_codigo, {
            "codigo": it.participante_codigo,
            "nombre": it.participante_nombre,
            "intentos": [],
            "tiene_activo": False,
            "ultimo_intento": it,
        })
        datos["intentos"].append(it)
        if it.estado == "en_progreso":
            datos["tiene_activo"] = True

    aprobados = reprobados = sin_nota = 0
    notas = []
    for datos in estudiantes.values():
        datos["total_intentos"] = len(datos["intentos"])
        califs = [i.calificacion for i in datos["intentos"] if intento_calificado(i)]
        if califs:
            mejor = max(califs)
            aprobado = mejor >= cuestionario.calificacion_aprobacion
            datos["mejor_calificacion"] = mejor
            datos["aprobado"] = aprobado
            datos["estado_final"] = "aprobado" if aprobado else "reprobado"
            notas.append(mejor)
            if aprobado:
                aprobados += 1
            else:
                reprobados += 1
        else:
            datos["mejor_calificacion"] = None
            datos["aprobado"] = False
            datos["estado_final"] = "en_curso" if datos["tiene_activo"] else "sin_nota"
            sin_nota += 1

    calificados = aprobados + reprobados
    metricas = {
        "total_estudiantes": len(estudiantes),
        "estudiantes_aprobados_count": aprobados,
        "estudiantes_reprobados_count": reprobados,
        "estudiantes_sin_nota_count": sin_nota,
        "estudiantes_calificados_count": calificados,
        # La tasa y el promedio se calculan solo sobre estudiantes con nota
        "tasa_aprobacion": round(aprobados / calificados * 100, 1) if calificados else 0,
        "promedio_calif": (
            (sum(notas) / len(notas)).quantize(Decimal("0.01")) if notas else Decimal("0.00")
        ),
    }
    return list(estudiantes.values()), metricas


def reporte_intentos(cuestionario) -> dict:
    """Contexto completo del panel de intentos: estudiantes agrupados, historial y métricas."""
    intentos = list(cuestionario.intentos.all().order_by("-fecha_inicio"))
    for intento in intentos:
        intento.dictamen = dictamen_intento(intento, cuestionario)
    estudiantes, metricas = resumen_por_estudiante(cuestionario, intentos)
    calificados = metricas["estudiantes_calificados_count"]
    resumen_aprobacion = (
        f"{number_format(metricas['tasa_aprobacion'], 1, use_l10n=True)} % de {calificados} con nota"
        if calificados else "Aún no hay estudiantes con nota"
    )
    return {
        "resumen_aprobacion": resumen_aprobacion,
        "estudiantes_agrupados": estudiantes,
        "intentos": intentos,
        "total_intentos_registrados": len(intentos),
        "total_preguntas": cuestionario.cuestionario_preguntas.count(),
        **metricas,
    }


def libro_excel_intentos(cuestionario, q: str = ""):
    """
    Libro .xlsx del reporte con tres hojas: Resumen, Notas definitivas
    (1 fila por estudiante) e Historial. `q` filtra por nombre o código.
    Retorna (workbook, nombre_archivo).
    """
    intentos = cuestionario.intentos.all().order_by("participante_codigo", "-fecha_inicio")
    q = (q or "").strip()
    if q:
        intentos = intentos.filter(
            Q(participante_nombre__icontains=q) | Q(participante_codigo__icontains=q)
        )
    intentos = list(intentos)
    estudiantes, metricas = resumen_por_estudiante(cuestionario, intentos)

    zona = timezone.get_current_timezone()

    def fecha_local(valor):
        # Excel no admite fechas con zona horaria: se exporta la hora local sin tzinfo
        return timezone.localtime(valor, zona).replace(tzinfo=None) if valor else None

    # Estilos institucionales
    azul = "186382"
    fill_cabecera = PatternFill("solid", fgColor=azul)
    font_cabecera = Font(bold=True, color="FFFFFF")
    borde = Border(bottom=Side(style="thin", color="E2E8F0"))
    estilo_dictamen = {
        "Aprobado": (PatternFill("solid", fgColor="F0F8E8"), Font(bold=True, color="2D6B14")),
        "Reprobado": (PatternFill("solid", fgColor="FEE2E2"), Font(bold=True, color="991B1B")),
    }
    fmt_nota = "0.00"
    fmt_fecha = "dd/mm/yyyy hh:mm"

    def escribir_tabla(ws, cabeceras, filas, anchos, formatos, col_dictamen=None):
        ws.append(cabeceras)
        for celda in ws[1]:
            celda.fill = fill_cabecera
            celda.font = font_cabecera
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 30
        for fila in filas:
            ws.append(fila)
        for idx, ancho in enumerate(anchos, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = ancho
        for fila in ws.iter_rows(min_row=2):
            for celda in fila:
                celda.border = borde
                fmt = formatos.get(celda.column)
                if fmt:
                    celda.number_format = fmt
            if col_dictamen:
                celda_d = fila[col_dictamen - 1]
                if celda_d.value in estilo_dictamen:
                    celda_d.fill, celda_d.font = estilo_dictamen[celda_d.value]
        ws.freeze_panes = "A2"
        if filas:
            ws.auto_filter.ref = ws.dimensions

    wb = Workbook()

    # --- Hoja 1: Resumen ---
    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = "Reporte de calificaciones"
    ws["A1"].font = Font(bold=True, size=14, color=azul)
    ws["A2"] = cuestionario.nombre
    ws["A2"].font = Font(bold=True, size=12)
    datos_resumen = [
        ("Generado", fecha_local(timezone.now())),
        ("Filtro aplicado", q or "Ninguno (todos los estudiantes)"),
        ("Escala de calificación", cuestionario.calificacion_maxima),
        ("Nota mínima de aprobación", cuestionario.calificacion_aprobacion),
        ("Intentos permitidos", cuestionario.intentos_permitidos),
        ("Tiempo límite (min)", cuestionario.tiempo_limite_minutos),
        ("", ""),
        ("Estudiantes evaluados", metricas["total_estudiantes"]),
        ("Estudiantes con nota", metricas["estudiantes_calificados_count"]),
        ("Aprobados", metricas["estudiantes_aprobados_count"]),
        ("Reprobados", metricas["estudiantes_reprobados_count"]),
        ("Sin nota (en curso o vencidos)", metricas["estudiantes_sin_nota_count"]),
        ("Tasa de aprobación (%)", metricas["tasa_aprobacion"]),
        ("Promedio de notas definitivas", metricas["promedio_calif"]),
        ("Intentos registrados", len(intentos)),
    ]
    for offset, (etiqueta, valor) in enumerate(datos_resumen, start=4):
        ws.cell(row=offset, column=1, value=etiqueta).font = Font(bold=True, color="475569")
        celda = ws.cell(row=offset, column=2, value=valor)
        celda.alignment = Alignment(horizontal="left")
        if etiqueta == "Generado":
            celda.number_format = fmt_fecha
        elif isinstance(valor, Decimal):
            celda.number_format = fmt_nota
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 40

    # --- Hoja 2: Notas definitivas (una fila por estudiante) ---
    ws = wb.create_sheet("Notas definitivas")
    etiquetas_estado = {
        "aprobado": "Aprobado",
        "reprobado": "Reprobado",
        "en_curso": "En curso",
        "sin_nota": "Sin nota",
    }
    filas = [
        [
            est["codigo"],
            est["nombre"],
            est["total_intentos"],
            cuestionario.intentos_permitidos,
            est["mejor_calificacion"],
            cuestionario.calificacion_maxima,
            etiquetas_estado[est["estado_final"]],
        ]
        for est in sorted(estudiantes, key=lambda e: e["nombre"].lower())
    ]
    escribir_tabla(
        ws,
        ["Código", "Nombre completo", "Intentos usados", "Intentos permitidos",
         "Nota definitiva", "Escala", "Dictamen"],
        filas,
        anchos=[16, 36, 14, 14, 14, 10, 16],
        formatos={5: fmt_nota, 6: fmt_nota},
        col_dictamen=7,
    )

    # --- Hoja 3: Historial completo de intentos ---
    ws = wb.create_sheet("Historial de intentos")
    filas = []
    for i in intentos:
        filas.append([
            i.id,
            i.participante_codigo,
            i.participante_nombre,
            fecha_local(i.fecha_inicio),
            fecha_local(i.fecha_fin),
            # Excel representa duraciones como fracción de día
            (i.duracion_segundos / 86400) if i.duracion_segundos else None,
            i.puntaje_obtenido,
            i.puntaje_total_posible,
            i.calificacion,
            i.get_estado_display(),
            dictamen_intento(i, cuestionario),
        ])
    escribir_tabla(
        ws,
        ["ID intento", "Código", "Nombre completo", "Inicio", "Entrega",
         "Duración (h:mm:ss)", "Puntaje obtenido", "Puntaje posible", "Calificación",
         "Estado", "Dictamen"],
        filas,
        anchos=[11, 16, 36, 18, 18, 14, 15, 15, 13, 14, 20],
        formatos={4: fmt_fecha, 5: fmt_fecha, 6: "[h]:mm:ss", 7: fmt_nota, 8: fmt_nota, 9: fmt_nota},
        col_dictamen=11,
    )

    nombre_archivo = f"notas_{slugify(cuestionario.nombre) or cuestionario.id}_{timezone.localdate():%Y%m%d}.xlsx"
    return wb, nombre_archivo


# ------------------------------------------------------------------------------
# Paneles de inicio
# ------------------------------------------------------------------------------

def periodo_academico(fecha=None) -> str:
    """Periodo semestral en curso, p. ej. 2026-II (julio a diciembre)."""
    fecha = fecha or timezone.localdate()
    return f"{fecha.year}-{'I' if fecha.month <= 6 else 'II'}"


def _cuestionarios_recientes(limite, base=None):
    return list(
        (base if base is not None else Cuestionario.objects.all()).annotate(
            num_preguntas=Count("cuestionario_preguntas", distinct=True),
            num_participantes=Count("intentos__participante_codigo", distinct=True),
        ).order_by("-id")[:limite]
    )


def panel_admin() -> dict:
    """Métricas globales y cobertura del banco por competencia."""
    categorias = list(
        Categoria.objects.annotate(
            num_preguntas=Count("preguntas", filter=Q(preguntas__activa=True))
        ).order_by("-num_preguntas", "nombre")
    )
    total_preguntas = sum(c.num_preguntas for c in categorias)
    for categoria in categorias:
        categoria.porcentaje = round(categoria.num_preguntas / total_preguntas * 100, 1) if total_preguntas else 0
    con_preguntas = sum(1 for c in categorias if c.num_preguntas)

    return {
        "periodo": periodo_academico(),
        "preguntas_activas": total_preguntas,
        "categorias": categorias,
        "categorias_count": len(categorias),
        "categorias_con_preguntas": con_preguntas,
        "cobertura": round(con_preguntas / len(categorias) * 100) if categorias else 0,
        "cuestionarios_count": Cuestionario.objects.count(),
        "intentos_count": Intento.objects.count(),
        "intentos_finalizados": Intento.objects.filter(estado="finalizado").count(),
        "preguntas_inactivas": Pregunta.objects.filter(activa=False).count(),
        "cuestionarios_recientes": _cuestionarios_recientes(5),
    }


def panel_docente(user) -> dict:
    """Resumen de trabajo del docente: sus cuestionarios y el banco de preguntas."""
    from apps.cuestionarios.acceso import editables

    propios = editables(user)
    por_estado = dict(
        propios.values_list("estado").annotate(total=Count("id")).values_list("estado", "total")
    )
    return {
        "periodo": periodo_academico(),
        "cuestionarios_count": sum(por_estado.values()),
        "publicados_count": por_estado.get("disponible", 0),
        "borradores_count": por_estado.get("borrador", 0),
        "preguntas_count": Pregunta.objects.filter(activa=True).count(),
        "preguntas_inactivas": Pregunta.objects.filter(activa=False).count(),
        "categorias_count": Categoria.objects.count(),
        "cuestionarios_recientes": _cuestionarios_recientes(4, propios),
    }
