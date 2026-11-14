# Actividad funcional del Simulador Saber TyT

## Proyecto y alcance

[Repositorio del proyecto](https://github.com/davidzambrano12/Cuestionarios-tyt)

- **Cuentas y académico** administran sesión, roles, cursos, períodos y matrículas. La matrícula delimita el acceso al cuestionario de curso.
- **Cuestionarios, banco e importaciones** permiten crear un borrador, validar la configuración, cargar el Excel, revisar errores y duplicados, asociar las preguntas válidas y publicar.
- **Evaluaciones** gestiona el temporizador, el guardado de respuestas, la entrega y la calificación persistente. La nota se muestra al entregar y la política de revisión controla si se muestran las respuestas y su retroalimentación.
- **Reportes** agrupa los intentos por estudiante. La nota definitiva es su mejor nota y los promedios excluyen participantes sin nota. El reporte del cuestionario incluye distribución por resultado y análisis por pregunta y eje de los intentos terminados, con porcentajes sobre respuestas contestadas. El acceso respeta los permisos del docente responsable y los roles administrativos autorizados.

La demostración utiliza un cuestionario de curso, sin contraseña adicional, con 20 minutos, un intento, nota máxima de 5,00 y aprobación desde 3,00. La contraseña adicional era opcional en la actividad.

## Resultados del escenario

| Estudiante | Cuantitativo | Lectura crítica | Nota | Dictamen |
| --- | --- | --- | ---: | --- |
| Ana | Acierto | Acierto | 5,00 | Aprobada |
| Luis | Acierto | Error | 2,50 | Reprobado |

Participaron 2 estudiantes, con 1 aprobado y 1 reprobado. El promedio fue **(5,00 + 2,50) ÷ 2 = 3,75** y la aprobación fue **1 ÷ 2 = 50 %**. Razonamiento Cuantitativo obtuvo **2/2 = 100 %**. Lectura Crítica presentó la mayor dificultad con **1/2 = 50 %**. La pregunta más difícil fue «¿Por qué salió tarde el bus?», con una respuesta incorrecta de dos.

## Reproducción en PowerShell

Con MariaDB local y las variables de conexión configuradas en el archivo de entorno, usa Python compatible con las dependencias declaradas y Microsoft Edge instalado.

```powershell
python -m pip install -r requirements-dev.txt
$env:E2E = "1"
$env:E2E_NAVEGADOR = "msedge"
python manage.py test pruebas_e2e.test_actividad_funcional --noinput
```

La prueba crea el curso, las cuentas y el cuestionario en la base de datos de pruebas de Django. Para socializar manualmente, usa una base local de demostración, crea dos estudiantes matriculados en un curso del docente y reproduce el flujo desde la creación del borrador hasta el reporte docente. Define las fechas alrededor de la hora de la presentación y selecciona el borrador como destino de la importación.

## Registro de pruebas

| Caso | Resultado observado | Estado | Incidencia pendiente |
| --- | --- | --- | --- |
| Configuración inválida | Se rechazan fechas invertidas y valores inválidos. La publicación también rechaza preguntas inexistentes o inactivas. | Aprobado | Ninguna |
| Importación válida y vinculación | Dos preguntas válidas se asociaron al borrador seleccionado. | Aprobado | Ninguna |
| Campos vacíos, respuesta Z y duplicado | La previsualización señaló una fila inválida y una duplicada. Se confirmaron únicamente las válidas. | Aprobado | Ninguna |
| Evaluación cerrada | La prueba de fechas comprueba que un cuestionario fuera de su ventana no genera intentos. | Aprobado | Ninguna |
| Límite de intentos | Tras entregar, cada estudiante conservó exactamente un intento al intentar iniciar de nuevo. | Aprobado | Ninguna |
| Entrega, persistencia y calificación | Quedaron guardadas dos respuestas y una fecha de entrega por estudiante, con notas de 5,00 y 2,50. | Aprobado | Ninguna |
| Consulta y estadísticas | El reporte coincide con las cuatro respuestas persistidas y el cálculo manual. | Aprobado | Ninguna |
| Restricción de acceso | El reporte respondió HTTP 403 a los estudiantes. La suite de visibilidad comprueba también el bloqueo a otro docente. | Aprobado | Ninguna |

## Ajustes aplicados

- El editor informa cuando se intenta publicar con preguntas inactivas, inexistentes o repetidas.
- El reporte del cuestionario reutiliza las consultas estadísticas existentes sobre el conjunto de intentos de esa evaluación.
- El recorrido de navegador acepta explícitamente la confirmación de importación que aparece al guardar un archivo con filas inválidas y comprueba la vinculación en MariaDB.
- La calificación y el autoguardado bloquean el mismo intento durante la escritura. Una segunda entrega conserva la fecha, las respuestas y la nota de la primera.

La suite completa con navegador ejecutó **157 pruebas con éxito**. Tras el ajuste de escritura de intentos, se repitieron **77 pruebas** de evaluación, cuestionarios, reportes y del recorrido integrado, todas aprobadas.

