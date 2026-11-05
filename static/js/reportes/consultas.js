/**
 * Consultas y reportes: filtros dependientes AÑO → PERÍODO → CURSO → ESTUDIANTE.
 * Cada lista solo ofrece valores compatibles con los filtros anteriores; si un
 * filtro padre cambia y la selección hija deja de ser válida, se limpia.
 * El servidor repite esta validación (no depende de este script).
 */
(function () {
  'use strict';

  const form = document.getElementById('form-consultas');
  const datos = document.getElementById('catalogo-consultas');
  if (!form || !datos) return;

  const catalogo = JSON.parse(datos.textContent);
  const campo = (nombre) => form.querySelector(`[data-filtro="${nombre}"]`);
  const anio = campo('anio');
  const periodo = campo('periodo');
  const curso = campo('curso');
  const estudiante = campo('estudiante');

  const periodoPorId = new Map(catalogo.periodos.map((p) => [String(p.id), p]));
  const cursoPorId = new Map(catalogo.cursos.map((c) => [String(c.id), c]));
  const estudiantePorCodigo = new Map(catalogo.estudiantes.map((e) => [e.codigo, e]));

  // Muestra solo las opciones válidas; «Todos» (valor vacío) siempre queda
  function limitar(select, esValida) {
    let actualValida = select.value === '';
    Array.from(select.options).forEach((opcion) => {
      if (!opcion.value) return;
      const valida = esValida(opcion.value);
      opcion.hidden = !valida;
      opcion.disabled = !valida;
      if (valida && opcion.value === select.value) actualValida = true;
    });
    if (!actualValida) select.value = '';
  }

  function periodosValidos() {
    return catalogo.periodos
      .filter((p) => !anio.value || String(p.anio) === anio.value)
      .map((p) => String(p.id));
  }

  function actualizar() {
    limitar(periodo, (id) => !anio.value || String(periodoPorId.get(id).anio) === anio.value);

    const periodos = periodo.value ? [periodo.value] : periodosValidos();
    limitar(curso, (id) => periodos.includes(String(cursoPorId.get(id).periodo)));

    limitar(estudiante, (codigo) => {
      const est = estudiantePorCodigo.get(codigo);
      if (!est || !est.cursos.length) return !anio.value && !periodo.value && !curso.value; // sin matrícula
      if (curso.value) return est.cursos.map(String).includes(curso.value);
      return est.periodos.map(String).some((p) => periodos.includes(p));
    });
  }

  [anio, periodo, curso].forEach((select) => select.addEventListener('change', actualizar));
  actualizar();

  // Ordenar: aplicar al elegir (sin JS hay un botón dentro de <noscript>)
  document.querySelectorAll('[data-enviar-al-cambiar]').forEach((select) => {
    select.addEventListener('change', () => select.form.submit());
  });
})();
