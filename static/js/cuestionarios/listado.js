/**
 * Listado de cuestionarios: búsqueda por texto y filtro por estado temporal
 * (disponible, programado, borrador o cerrado según las fechas).
 */
(function () {
  'use strict';

  const raiz = document.getElementById('listado-cuestionarios');
  const buscador = document.getElementById('filtro-texto');
  const chips = [...raiz.querySelectorAll('.chip-filtro')];
  const tarjetas = [...raiz.querySelectorAll('.tarjeta-listado')];
  const sinResultados = document.getElementById('sin-resultados');
  let estado = 'todos';

  function filtrar() {
    const q = buscador.value.toLowerCase().trim();
    let visibles = 0;
    tarjetas.forEach((tarjeta) => {
      const visible = (!q || tarjeta.dataset.texto.includes(q)) && (estado === 'todos' || tarjeta.dataset.estado === estado);
      tarjeta.hidden = !visible;
      if (visible) visibles += 1;
    });
    sinResultados.hidden = !(tarjetas.length && visibles === 0);
  }

  function seleccionar(nuevo) {
    estado = nuevo;
    chips.forEach((chip) => {
      const activo = chip.dataset.filtro === nuevo;
      chip.classList.toggle('active', activo);
      chip.setAttribute('aria-pressed', String(activo));
    });
    filtrar();
  }

  chips.forEach((chip) => chip.addEventListener('click', () => seleccionar(chip.dataset.filtro)));
  buscador.addEventListener('input', filtrar);
  raiz.addEventListener('click', (evento) => {
    if (!evento.target.closest('[data-accion="limpiar-filtros"]')) return;
    buscador.value = '';
    seleccionar('todos');
  });
})();
