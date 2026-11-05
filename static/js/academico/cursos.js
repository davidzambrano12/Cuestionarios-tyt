/**
 * Cursos y matrículas: filtrar matriculados, seleccionar estudiantes para
 * matricular y aplicar el período al elegirlo en el listado.
 */
(function () {
  'use strict';

  // Listado: cambiar de período aplica el filtro
  document.querySelectorAll('[data-enviar-al-cambiar]').forEach((select) => {
    select.addEventListener('change', () => select.form.submit());
  });

  // Selección de candidatos
  const form = document.getElementById('form-matricular');
  if (form) {
    const casillas = Array.from(form.querySelectorAll('[data-candidato]'));
    const todos = form.querySelector('[data-seleccionar-todos]');
    const boton = form.querySelector('[data-ref="matricular"]');
    const texto = form.querySelector('[data-ref="matricular-texto"]');
    const actualizar = () => {
      const n = casillas.filter((c) => c.checked).length;
      boton.disabled = n === 0;
      texto.textContent = n ? `Matricular ${n} estudiante${n === 1 ? '' : 's'}` : 'Matricular seleccionados';
      if (todos) {
        todos.checked = n === casillas.length;
        todos.indeterminate = n > 0 && n < casillas.length;
      }
    };
    casillas.forEach((c) => c.addEventListener('change', actualizar));
    if (todos) todos.addEventListener('change', () => { casillas.forEach((c) => { c.checked = todos.checked; }); actualizar(); });
    actualizar();
  }

  // Filtrar matriculados
  const filtro = document.getElementById('filtro-matriculados');
  if (filtro) {
    const filas = Array.from(document.querySelectorAll('.fila-matricula'));
    const vacio = document.querySelector('#matriculados .fila-sin-resultados');
    const normalizar = (t) => (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    filtro.addEventListener('input', () => {
      const q = normalizar(filtro.value.trim());
      let visibles = 0;
      filas.forEach((fila) => {
        const ok = !q || normalizar(fila.dataset.texto).includes(q);
        fila.hidden = !ok;
        if (ok) visibles += 1;
      });
      vacio.hidden = visibles > 0;
    });
  }
})();
