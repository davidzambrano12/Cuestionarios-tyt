/**
 * Reporte de intentos: pestañas, búsqueda, filtros por resultado, acordeón
 * de intentos por estudiante y enlace de exportación que respeta la búsqueda.
 * Datos: #reporte-intentos[data-url-exportar].
 */
(function () {
  'use strict';

  const raiz = document.getElementById('reporte-intentos');
  const buscador = document.getElementById('filtro-busqueda');
  const contador = document.getElementById('contador-resultados');
  const exportar = raiz.querySelector('[data-ref="exportar"]');
  const exportarTexto = raiz.querySelector('[data-ref="exportar-texto"]');
  const urlExportar = raiz.dataset.urlExportar;
  const pestanas = [...raiz.querySelectorAll('[role="tab"]')];
  const chips = [...raiz.querySelectorAll('.chip-filtro')];

  let vistaActual = 'estudiantes';
  let estadoActual = 'todos';

  function cambiarVista(vista, enfocar = false) {
    vistaActual = vista;
    pestanas.forEach((tab) => {
      const activa = tab.dataset.vista === vista;
      tab.classList.toggle('active', activa);
      tab.setAttribute('aria-selected', String(activa));
      tab.tabIndex = activa ? 0 : -1;
      document.getElementById(`vista-${tab.dataset.vista}`).hidden = !activa;
      if (activa && enfocar) tab.focus();
    });
    aplicarFiltros();
  }

  function seleccionarEstado(estado) {
    estadoActual = estado;
    chips.forEach((chip) => {
      const activo = chip.dataset.filtro === estado;
      chip.classList.toggle('active', activo);
      chip.setAttribute('aria-pressed', String(activo));
    });
    aplicarFiltros();
  }

  function cerrarDetalle(fila) {
    const detalle = document.getElementById(fila.dataset.detalle);
    if (detalle) detalle.hidden = true;
    const boton = fila.querySelector('[data-acordeon]');
    if (boton) boton.setAttribute('aria-expanded', 'false');
  }

  function filtrarFilas(selector, coincide) {
    const filas = [...raiz.querySelectorAll(selector)];
    let visibles = 0;
    filas.forEach((fila) => {
      const visible = coincide(fila);
      fila.hidden = !visible;
      if (visible) visibles += 1;
      else if (fila.dataset.detalle) cerrarDetalle(fila);
    });
    return { total: filas.length, visibles };
  }

  function aplicarFiltros() {
    const q = buscador.value.toLowerCase().trim();
    const coincide = (fila) => (fila.dataset.texto || '').includes(q)
      && (estadoActual === 'todos' || fila.dataset.estado === estadoActual);

    const est = filtrarFilas('.fila-estudiante', coincide);
    const hist = filtrarFilas('.fila-historial', coincide);
    document.querySelector('#vista-estudiantes .fila-sin-resultados').hidden = !(est.total && est.visibles === 0);
    document.querySelector('#vista-historial .fila-sin-resultados').hidden = !(hist.total && hist.visibles === 0);

    const hayFiltro = q !== '' || estadoActual !== 'todos';
    const actual = vistaActual === 'estudiantes' ? [est, 'estudiantes'] : [hist, 'intentos'];
    contador.textContent = hayFiltro ? `Mostrando ${actual[0].visibles} de ${actual[0].total} ${actual[1]}` : '';

    // La exportación respeta la búsqueda por nombre o código
    exportar.href = q ? `${urlExportar}?q=${encodeURIComponent(q)}` : urlExportar;
    exportarTexto.textContent = q ? 'Exportar búsqueda a Excel' : 'Exportar a Excel';
  }

  pestanas.forEach((tab) => tab.addEventListener('click', () => cambiarVista(tab.dataset.vista)));
  // Flechas entre pestañas (patrón WAI-ARIA)
  raiz.querySelector('[role="tablist"]').addEventListener('keydown', (evento) => {
    if (evento.key !== 'ArrowRight' && evento.key !== 'ArrowLeft') return;
    cambiarVista(vistaActual === 'estudiantes' ? 'historial' : 'estudiantes', true);
  });

  chips.forEach((chip) => chip.addEventListener('click', () => seleccionarEstado(chip.dataset.filtro)));
  buscador.addEventListener('input', aplicarFiltros);

  raiz.addEventListener('click', (evento) => {
    const acordeon = evento.target.closest('[data-acordeon]');
    if (acordeon) {
      const detalle = document.getElementById(acordeon.dataset.acordeon);
      const abrir = detalle.hidden;
      detalle.hidden = !abrir;
      acordeon.setAttribute('aria-expanded', String(abrir));
      return;
    }
    if (evento.target.closest('[data-accion="limpiar-filtros"]')) {
      buscador.value = '';
      seleccionarEstado('todos');
    }
  });
})();
