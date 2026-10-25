"""
Lógica de importación de preguntas desde la plantilla de Excel.

Flujo (coincide con lo pedido en el taller):
    1. El usuario sube el Excel -> se llama `procesar_archivo(ruta, commit=False)`
       para VALIDAR sin guardar nada. La vista muestra el resultado: filas
       válidas, duplicadas y con error (indicando el número de fila de Excel).
    2. Si el usuario confirma -> se llama de nuevo a `procesar_archivo(ruta,
       commit=True)`. Esta vez sí inserta en la base de datos dentro de una
       transacción, y registra el resumen en la tabla `importaciones`.

La misma función se usa para previsualizar y para confirmar, así la
validación nunca se desincroniza de lo que realmente se guarda.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import openpyxl
from django.db import IntegrityError, transaction

from preguntas.models import Categoria, CuestionarioPregunta, Importacion, OpcionRespuesta, Pregunta

COLUMNAS = [
    "categoria", "tipo", "texto_base", "pregunta",
    "opcion_a", "opcion_b", "opcion_c", "opcion_d",
    "respuesta_correcta", "retroalimentacion", "puntaje",
]
TIPOS_VALIDOS = {"MULTIPLE", "V_F"}
LETRAS_OPCION = ["A", "B", "C", "D"]


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _normalizar(texto: str) -> str:
    """Minúsculas y espacios colapsados, para que la huella no cambie por
    mayúsculas o espacios de más."""
    return re.sub(r"\s+", " ", texto.strip().lower())


def calcular_huella(enunciado: str, opciones_texto: list[str]) -> str:
    base = _normalizar(enunciado) + "|" + "|".join(_normalizar(o) for o in opciones_texto)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


@dataclass
class FilaImportacion:
    fila_excel: int
    estado: str  # "valida" | "duplicada" | "error"
    categoria: str = ""
    tipo: str = ""
    enunciado: str = ""
    errores: list[str] = field(default_factory=list)
    # Solo presentes cuando estado == "valida"
    texto_base: str = ""
    retroalimentacion: str = ""
    puntaje: Decimal | None = None
    opciones: list[tuple[str, bool]] = field(default_factory=list)  # (texto, es_correcta)
    huella: str = ""
    valores_crudos: dict = field(default_factory=dict)

    @property
    def json_data(self) -> str:
        resp_corr = self.valores_crudos.get("respuesta_correcta", "")
        if not resp_corr and self.opciones:
            for idx, (_, es_corr) in enumerate(self.opciones):
                if es_corr and idx < 4:
                    resp_corr = ["A", "B", "C", "D"][idx]
                    break

        opc_a = self.valores_crudos.get("opcion_a", "") or (self.opciones[0][0] if len(self.opciones) > 0 else "")
        opc_b = self.valores_crudos.get("opcion_b", "") or (self.opciones[1][0] if len(self.opciones) > 1 else "")
        opc_c = self.valores_crudos.get("opcion_c", "") or (self.opciones[2][0] if len(self.opciones) > 2 else "")
        opc_d = self.valores_crudos.get("opcion_d", "") or (self.opciones[3][0] if len(self.opciones) > 3 else "")

        tipo_limpio = (self.valores_crudos.get("tipo", "") or self.tipo or "").upper().strip()
        if tipo_limpio not in ("MULTIPLE", "V_F"):
            tipo_limpio = ""

        data = {
            "fila_excel": self.fila_excel,
            "categoria": self.valores_crudos.get("categoria", "") or self.categoria,
            "tipo": tipo_limpio,
            "texto_base": self.valores_crudos.get("texto_base", "") or self.texto_base,
            "pregunta": self.valores_crudos.get("pregunta", "") or self.enunciado,
            "opcion_a": opc_a,
            "opcion_b": opc_b,
            "opcion_c": opc_c,
            "opcion_d": opc_d,
            "respuesta_correcta": resp_corr,
            "retroalimentacion": self.valores_crudos.get("retroalimentacion", "") or self.retroalimentacion,
            "puntaje": str(self.valores_crudos.get("puntaje", "")) or (str(self.puntaje) if self.puntaje else "1.0"),
            "errores": self.errores,
        }
        return json.dumps(data)


@dataclass
class ResultadoImportacion:
    nombre_archivo: str
    total_filas: int = 0
    filas: list[FilaImportacion] = field(default_factory=list)
    importacion_id: int | None = None

    @property
    def validas(self):
        return [f for f in self.filas if f.estado == "valida"]

    @property
    def duplicadas(self):
        return [f for f in self.filas if f.estado == "duplicada"]

    @property
    def con_error(self):
        return [f for f in self.filas if f.estado == "error"]

    @property
    def resultado_global(self) -> str:
        if not self.validas:
            return "fallida"
        if self.duplicadas or self.con_error:
            return "parcial"
        return "exitosa"


def _validar_fila(valores: dict) -> FilaImportacion:
    """Valida una fila ya leída del Excel (sin tocar la base de datos)."""
    errores = []

    categoria = _texto(valores["categoria"])
    tipo = _texto(valores["tipo"]).upper()
    texto_base = _texto(valores["texto_base"])
    enunciado = _texto(valores["pregunta"])
    opciones_crudas = {letra: _texto(valores[f"opcion_{letra.lower()}"]) for letra in LETRAS_OPCION}
    respuesta_correcta = _texto(valores["respuesta_correcta"]).upper()
    retroalimentacion = _texto(valores["retroalimentacion"])
    puntaje_crudo = valores["puntaje"]

    if not categoria:
        errores.append("falta la categoría")
    if tipo not in TIPOS_VALIDOS:
        errores.append("tipo inválido (usa MULTIPLE o V_F)")
    if not enunciado:
        errores.append("falta el enunciado de la pregunta")

    puntaje = None
    if puntaje_crudo in (None, ""):
        errores.append("falta el puntaje")
    else:
        try:
            puntaje = Decimal(str(puntaje_crudo))
            if puntaje <= 0:
                errores.append("el puntaje debe ser mayor que cero")
        except (InvalidOperation, ValueError):
            errores.append("el puntaje no es un número válido")

    opciones: list[tuple[str, bool]] = []
    if tipo == "MULTIPLE":
        faltantes = [l for l in LETRAS_OPCION if not opciones_crudas[l]]
        if faltantes:
            errores.append(f"faltan opciones: {', '.join(opciones_crudas[l] or l for l in faltantes)}")
        if respuesta_correcta not in LETRAS_OPCION:
            errores.append("respuesta_correcta debe ser A, B, C o D")
        if not errores:
            opciones = [(opciones_crudas[l], l == respuesta_correcta) for l in LETRAS_OPCION]
    elif tipo == "V_F":
        if not opciones_crudas["A"] or not opciones_crudas["B"]:
            errores.append("faltan opcion_a / opcion_b (Verdadero/Falso)")
        if respuesta_correcta not in ("A", "B"):
            errores.append("respuesta_correcta debe ser A o B en preguntas V_F")
        if not errores:
            opciones = [
                (opciones_crudas["A"], respuesta_correcta == "A"),
                (opciones_crudas["B"], respuesta_correcta == "B"),
            ]
    # si el tipo ya era inválido, no seguimos validando opciones de un tipo que no existe

    fila = FilaImportacion(
        fila_excel=0,  # se asigna afuera
        estado="error" if errores else "valida",
        categoria=categoria,
        tipo=tipo,
        enunciado=enunciado,
        errores=errores,
        texto_base=texto_base,
        retroalimentacion=retroalimentacion,
        puntaje=puntaje,
        opciones=opciones,
        valores_crudos={k: _texto(valores.get(k, "")) for k in COLUMNAS},
    )
    if not errores:
        fila.huella = calcular_huella(enunciado, [o[0] for o in opciones])
    return fila


def procesar_archivo(ruta_archivo: str, nombre_archivo: str, *, commit: bool = False,
                      cuestionario_id: int | None = None) -> ResultadoImportacion:
    """Lee y valida el Excel. Si commit=True, además guarda en la base de
    datos dentro de una transacción y registra la fila en `importaciones`."""
    wb = openpyxl.load_workbook(ruta_archivo, data_only=True)
    ws = wb["preguntas"] if "preguntas" in wb.sheetnames else wb.active

    resultado = ResultadoImportacion(nombre_archivo=nombre_archivo)
    huellas_vistas_en_archivo: dict[str, int] = {}
    huellas_existentes = set(Pregunta.objects.values_list("huella_contenido", flat=True))

    for fila_excel, row in enumerate(ws.iter_rows(min_row=2, max_col=len(COLUMNAS), values_only=True), start=2):
        if row is None or all(v in (None, "") for v in row):
            continue  # fila completamente vacía, se ignora sin contar error

        valores = dict(zip(COLUMNAS, row))
        fila = _validar_fila(valores)
        fila.fila_excel = fila_excel
        resultado.total_filas += 1

        if fila.estado == "valida":
            if fila.huella in huellas_existentes or fila.huella in huellas_vistas_en_archivo:
                origen = huellas_vistas_en_archivo.get(fila.huella)
                fila.estado = "duplicada"
                if origen:
                    fila.errores = [f"misma pregunta que la fila {origen} de este archivo"]
                else:
                    fila.errores = ["esta pregunta ya existe en el banco de preguntas"]
            else:
                huellas_vistas_en_archivo[fila.huella] = fila_excel

        resultado.filas.append(fila)

    wb.close()

    if commit:
        _guardar_resultado(resultado, cuestionario_id)

    return resultado


@transaction.atomic
def _guardar_resultado(resultado: ResultadoImportacion, cuestionario_id: int | None) -> None:
    orden = 0
    for fila in resultado.validas:
        categoria, _ = Categoria.objects.get_or_create(nombre=fila.categoria)
        try:
            with transaction.atomic():
                pregunta = Pregunta.objects.create(
                    categoria=categoria,
                    tipo=fila.tipo,
                    texto_base=fila.texto_base or None,
                    enunciado=fila.enunciado,
                    retroalimentacion=fila.retroalimentacion or None,
                    puntaje=fila.puntaje,
                    huella_contenido=fila.huella,
                    activa=True,
                )
                for pos, (texto_opcion, es_correcta) in enumerate(fila.opciones):
                    OpcionRespuesta.objects.create(
                        pregunta=pregunta, texto=texto_opcion,
                        es_correcta=es_correcta, orden=pos,
                    )
                if cuestionario_id:
                    orden += 1
                    CuestionarioPregunta.objects.create(
                        cuestionario_id=cuestionario_id, pregunta=pregunta, orden=orden,
                    )
        except IntegrityError:
            # Otra importación guardó la misma huella justo antes que esta
            # (carrera entre la previsualización y la confirmación).
            fila.estado = "duplicada"
            fila.errores = ["se guardó como duplicada: otra importación la registró primero"]

    importacion = Importacion.objects.create(
        cuestionario_id=cuestionario_id,
        nombre_archivo=resultado.nombre_archivo,
        total_filas=resultado.total_filas,
        filas_validas=len(resultado.validas),
        filas_duplicadas=len(resultado.duplicadas),
        filas_con_error=len(resultado.con_error),
        resultado=resultado.resultado_global,
    )
    resultado.importacion_id = importacion.id


def actualizar_fila_excel(ruta_archivo: str, fila_excel: int, nuevos_valores: dict) -> None:
    """Actualiza una fila en el archivo Excel con las correcciones introducidas por el usuario."""
    wb = openpyxl.load_workbook(ruta_archivo)
    ws = wb["preguntas"] if "preguntas" in wb.sheetnames else wb.active

    for col_idx, col_name in enumerate(COLUMNAS, start=1):
        if col_name in nuevos_valores:
            val = nuevos_valores[col_name]
            if col_name == "puntaje":
                try:
                    val = float(val) if val else 1.0
                except (ValueError, TypeError):
                    val = str(val)
            elif col_name in ("tipo", "respuesta_correcta"):
                val = str(val).strip().upper()
            else:
                val = str(val).strip()
            ws.cell(row=fila_excel, column=col_idx, value=val)

    wb.save(ruta_archivo)
    wb.close()

