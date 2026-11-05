# Módulo de consultas, reportes y exportación a Excel

Pantalla: **Consultas y reportes** en el menú del administrador y del docente (`/reportes/consultas/`).

## 1. Modelo de datos y ruta hasta la calificación

```mermaid
erDiagram
    periodos_academicos ||--o{ cursos : "tiene"
    cursos ||--o{ matriculas : "agrupa"
    auth_user ||--o{ matriculas : "estudiante"
    auth_user ||--o{ cursos : "docente a cargo"
    cursos ||--o{ intentos : "curso al presentar"
    cuestionarios ||--o{ intentos : "simulacro"
    intentos ||--o{ respuestas_intento : "respuestas"
    preguntas ||--o{ respuestas_intento : ""
    categorias ||--o{ preguntas : "eje temático"
```

| Filtro | Origen en la base de datos |
|---|---|
| Año | `periodos_academicos.anio` |
| Período | `periodos_academicos` (`anio`-`numero`, p. ej. 2026-2) |
| Curso / grupo | `cursos`: una asignatura dictada a un grupo en un período (p. ej. *Electiva Profesional III · G01 · 2026-2*), con programa, semestre y docente a cargo |
| Eje temático | `categorias`, a través de `respuestas_intento → preguntas` |
| Estudiante | `intentos.participante_codigo` = código institucional del estudiante matriculado |

**Ruta:** estudiante → `matriculas` → `cursos` → `periodos_academicos`. Al iniciar un intento se guarda en `intentos.curso_id` el curso vigente del estudiante (período que incluye la fecha). Así un reporte histórico no cambia si después lo matriculan en otro curso. Para intentos anteriores al módulo: `python manage.py asignar_cursos_intentos`.

Cada intento tiene estudiante (`participante_codigo`, `participante_nombre`), evaluación (`cuestionario_id`), fecha (`fecha_inicio`, `fecha_fin`), estado (`en_progreso`, `finalizado`, `vencido`) y calificación.

**Fórmula de la nota** (al entregar):

```
calificacion = puntaje_obtenido / puntaje_total_posible × calificacion_maxima
nota sobre 5,0 = calificacion × 5 / calificacion_maxima
aprobado = calificacion ≥ calificacion_aprobacion del simulacro
```

## 2. Reglas de cálculo

- **Escala:** todas las notas se muestran y exportan sobre 5,0, con dos decimales.
- **Umbral de aprobación:** el de cada simulacro. La pantalla lo muestra junto a los indicadores.
- **Intentos que cuentan:** promedio, mínima, máxima y aprobación usan solo intentos **terminados** (finalizados o vencidos, con nota). Los intentos en progreso se listan, pero no cuentan; la pantalla indica cuántos hay.
- **Estudiantes e intentos:** se cuentan por separado. "Estudiantes evaluados" son códigos distintos; un estudiante puede tener varios intentos.
- **Por eje:** se cuentan las respuestas contestadas (aciertos, errores y porcentaje). No se calcula nota por eje, porque el sistema no define una regla para convertir aciertos en calificación.
- **Los reportes no modifican datos.** Solo leen con el ORM.

## 3. Filtros jerárquicos

AÑO → PERÍODO → CURSO → EJE → ESTUDIANTE, cada uno con la opción "Todos".

- En la pantalla, cada lista solo ofrece valores compatibles con la anterior. Al cambiar un filtro padre, se limpia la selección hija que dejó de ser válida.
- El servidor repite la validación: un valor incompatible se quita y se avisa.
- "Limpiar filtros" vuelve a la consulta general.
- La tabla de calificaciones se pagina de 10 en 10, se ordena por fecha, nombre o nota (de mayor a menor) y conserva los filtros entre páginas.

## 4. Consultas y archivos Excel

| N.º | Consulta | Dónde |
|---|---|---|
| 1 | Consolidado general | Indicadores superiores |
| 2 | Resultados por año y período | Pestaña "Por período" |
| 3 | Resultados por curso | Pestaña "Por curso" |
| 4 | Desempeño por eje temático | Pestaña "Por eje temático" |
| 5 | Calificaciones por estudiante | Pestaña "Calificaciones" |
| 6 | Historial individual (con evolución) | Pestaña "Historial individual" |
| 7 | Preguntas de mayor dificultad | Pestaña "Preguntas difíciles" |

| Excel | Contenido |
|---|---|
| A · Consolidado | Año, período, curso, estudiante, identificación, simulacro, fecha, calificación y estado. Hoja adicional con el promedio por estudiante |
| B · Por eje | Año, período, curso, eje, respuestas registradas, contestadas, aciertos, errores, sin responder, % de aciertos y nota promedio ("No definida") |
| C · Historial | Estudiante, curso, período, simulacro, fecha, respondidas, aciertos, errores y nota final. Un intento por fila, en orden cronológico |

Cada archivo:
- incluye el nombre del reporte, la fecha de generación, los filtros activos y las reglas de cálculo;
- tiene un nombre descriptivo, por ejemplo `reporte_consolidado_2026-2_sexto-a_20261105-1030.xlsx`;
- contiene **todos** los registros filtrados, no solo la página visible.

Sin registros, se descarga igual con los encabezados y el aviso "Sin registros para los filtros aplicados.".

## 5. Seguridad

- La vista y la exportación exigen sesión y el permiso `resultados.consultar_todos`. Los estudiantes reciben 403.
- **Administrador:** ve todos los cursos.
- **Docente:** solo ve los cursos que tiene a cargo (`cursos.docente_id`). Si pide en la URL un curso o período ajeno, el servidor responde **403**, tanto en la pantalla como en el Excel.
- El estudiante solo ve sus propios resultados en su panel.

## 6. Datos de prueba y demostración

```bash
python manage.py datos_demo_consultas            # 3 períodos, 5 cursos, 12 estudiantes, ~90 intentos
python manage.py datos_demo_consultas --limpiar  # borra solo esos datos
```

- El grupo 01 de cada asignatura queda a cargo del primer docente activo.

## 7. Cuestionarios institucionales y de curso

| Visibilidad | Quién lo presenta | Quién lo crea y edita |
|---|---|---|
| **Institucional** | Cualquier estudiante activo | Administrador o quien tenga el permiso `cuestionarios.publicar` |
| **De curso** | Solo los matriculados en los cursos asignados, en el período vigente | Su creador (en sus cursos) o un administrador |

- **Cada cuestionario guarda su creador.** El docente edita y ve el reporte por cuestionario solo de los suyos.
  - Los institucionales los puede previsualizar, y los resultados de sus estudiantes en ellos los ve en Consultas.
- **El servidor rechaza** que un estudiante inicie por URL un cuestionario de un curso ajeno.
- **La portada pública** solo anuncia los institucionales.
- **Atribución del intento:**
  - De curso: cuenta en el curso del estudiante entre los asignados.
  - Institucional: si el estudiante tiene un solo curso vigente, cuenta en ese. Si tiene varios, elige para cuál lo presenta antes de empezar. Si no tiene ninguno, queda sin curso.
- **Período:** cada intento guarda el período según su fecha, así cuenta en los reportes por año y período aunque no tenga curso.
- **En Consultas,** el filtro "Tipo de simulacro" separa los institucionales de los de curso.
- **Datos anteriores:** los cuestionarios que existían antes quedaron institucionales, que es como funcionaban.

## 8. Cómo se matricula un estudiante

La matrícula la hace la institución, no el estudiante (RULE-04). Se hace en el menú **Cursos**:

1. **El administrador crea el período académico** con "Nuevo período" (año, número y fechas).
2. **Se crea el curso:** asignatura, grupo, programa, semestre y docente. El docente también puede crearlo, y queda a su cargo.
3. **Se matricula a los estudiantes** desde el detalle del curso: se buscan por nombre, código o documento, se marcan (o "Seleccionar todos") y se pulsa "Matricular".
   - Los intentos que esos estudiantes ya presentaron en el período sin curso quedan asociados automáticamente.
   - Si un estudiante ya está en otro curso del mismo período, se avisa. Sus intentos nuevos se asignan a un solo curso: el primero en orden alfabético.
4. **Retirar a un estudiante** pide confirmación, y no se permite si ya tiene intentos en el curso, para conservar el historial. Al cerrar el período, el curso se marca como inactivo.

El docente solo ve y gestiona sus cursos. Si en Cursos o en Consultas aparecen intentos terminados sin curso, el administrador recibe un aviso. Los períodos, cursos y matrículas también se pueden editar en `/admin/`.
- Pruebas automáticas: `apps/reportes/tests/test_consultas.py` y `pruebas_e2e/test_consultas.py`.
