/**
 * Revisión de la importación:
 *   - filtra las tarjetas por estado, texto y categoría;
 *   - recorta los textos largos con un botón «Ver más»;
 *   - abre el modal de edición con los datos de la fila (atributo data-fila,
 *     JSON escapado por la plantilla) y ajusta las opciones según el tipo.
 * Todo el texto del Excel se asigna con value o textContent, nunca como HTML.
 */
(function () {
  'use strict';

  const raiz = document.getElementById('revision-importacion');
  if (!raiz) return;

  /* ------------------------------------------------------------ Filtros */

  const tarjetas = Array.from(raiz.querySelectorAll('.pregunta-importada'));
  const chips = Array.from(raiz.querySelectorAll('[data-filtro-estado]'));
  const buscador = document.getElementById('filtro-texto');
  const selectorCategoria = document.getElementById('filtro-categoria');
  const contador = document.getElementById('contador-revision');
  const sinResultados = document.getElementById('revision-sin-resultados');
  let estadoActivo = 'todas';

  function normalizar(texto) {
    return (texto || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function filtrar() {
    const consulta = normalizar(buscador ? buscador.value.trim() : '');
    const categoria = selectorCategoria ? selectorCategoria.value : '';
    let visibles = 0;
    tarjetas.forEach((tarjeta) => {
      const coincide =
        (estadoActivo === 'todas' || tarjeta.dataset.estado === estadoActivo) &&
        (!categoria || tarjeta.dataset.categoria === categoria) &&
        (!consulta || normalizar(tarjeta.dataset.busqueda).includes(consulta));
      tarjeta.hidden = !coincide;
      if (coincide) visibles += 1;
    });
    if (contador) contador.textContent = `Mostrando ${visibles} de ${tarjetas.length}`;
    if (sinResultados) sinResultados.hidden = visibles > 0 || tarjetas.length === 0;
  }

  function elegirEstado(estado) {
    estadoActivo = estado;
    chips.forEach((chip) => {
      const activo = chip.dataset.filtroEstado === estado;
      chip.classList.toggle('active', activo);
      chip.setAttribute('aria-pressed', String(activo));
    });
    filtrar();
  }

  chips.forEach((chip) => chip.addEventListener('click', () => elegirEstado(chip.dataset.filtroEstado)));
  if (buscador) buscador.addEventListener('input', filtrar);
  if (selectorCategoria) selectorCategoria.addEventListener('change', filtrar);
  raiz.addEventListener('click', (evento) => {
    if (!evento.target.closest('[data-accion="limpiar-filtros"]')) return;
    if (buscador) buscador.value = '';
    if (selectorCategoria) selectorCategoria.value = '';
    elegirEstado('todas');
  });

  // Un enlace a otra fila (duplicadas) debe mostrarla aunque haya filtros activos
  raiz.addEventListener('click', (evento) => {
    const enlace = evento.target.closest('a[href^="#fila-"]');
    if (!enlace) return;
    const destino = document.getElementById(enlace.getAttribute('href').slice(1));
    if (destino && destino.hidden) {
      if (buscador) buscador.value = '';
      if (selectorCategoria) selectorCategoria.value = '';
      elegirEstado('todas');
    }
  });

  /* ------------------------------------------------------------ Ver más */

  raiz.querySelectorAll('[data-recortable]').forEach((bloque, indice) => {
    // Solo los textos que de verdad exceden el recorte llevan el botón
    if (bloque.scrollHeight <= bloque.clientHeight + 2) {
      bloque.classList.remove('texto-recortable');
      return;
    }
    bloque.id = bloque.id || `texto-recortable-${indice}`;
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'ver-mas';
    boton.setAttribute('aria-controls', bloque.id);
    boton.setAttribute('aria-expanded', 'false');
    boton.textContent = 'Ver más';
    boton.addEventListener('click', () => {
      const expandido = bloque.classList.toggle('texto-recortable--abierto');
      boton.setAttribute('aria-expanded', String(expandido));
      boton.textContent = expandido ? 'Ver menos' : 'Ver más';
    });
    bloque.after(boton);
  });

  /* ------------------------------------------------------------ Edición */

  const form = document.getElementById('form-correccion');
  const campos = form.elements;
  const cajaErrores = document.querySelector('#modal-correccion [data-ref="errores"]');
  const listaErrores = document.querySelector('#modal-correccion [data-ref="lista-errores"]');

  function aplicarTipo() {
    const vf = campos.tipo.value === 'V_F';
    ['C', 'D'].forEach((letra) => {
      form.querySelectorAll(`[data-opcion="${letra}"]`).forEach((el) => { el.hidden = vf; });
      const input = campos[`opcion_${letra.toLowerCase()}`];
      input.disabled = vf;
      input.required = campos.tipo.value === 'MULTIPLE';
    });
    if (vf) {
      if (!campos.opcion_a.value) campos.opcion_a.value = 'Verdadero';
      if (!campos.opcion_b.value) campos.opcion_b.value = 'Falso';
      if (['C', 'D'].includes(campos.respuesta_correcta.value)) campos.respuesta_correcta.value = 'A';
    }
  }

  function abrir(boton) {
    let datos;
    try {
      datos = JSON.parse(boton.dataset.fila);
    } catch (error) {
      window.mostrarNotificacion('No se pudieron leer los datos de la fila.', 'error', 'Importación');
      return;
    }
    form.reset();
    campos.fila_excel.value = boton.dataset.corregir;
    document.querySelector('#modal-correccion [data-ref="fila"]').textContent = `la fila ${boton.dataset.corregir}`;
    campos.categoria.value = datos.categoria || '';
    const tipo = (datos.tipo || '').toUpperCase().trim();
    campos.tipo.value = ['MULTIPLE', 'V_F'].includes(tipo) ? tipo : '';
    campos.puntaje.value = datos.puntaje || '1.0';
    campos.texto_base.value = datos.texto_base || '';
    campos.pregunta.value = datos.pregunta || '';
    ['a', 'b', 'c', 'd'].forEach((l) => { campos[`opcion_${l}`].value = datos[`opcion_${l}`] || ''; });
    campos.respuesta_correcta.value = (datos.respuesta_correcta || 'A').toUpperCase();
    campos.retroalimentacion.value = datos.retroalimentacion || '';

    listaErrores.replaceChildren(...(datos.errores || []).map((texto) => {
      const li = document.createElement('li');
      li.textContent = texto.charAt(0).toUpperCase() + texto.slice(1);
      return li;
    }));
    cajaErrores.hidden = !(datos.errores && datos.errores.length);
    aplicarTipo();
    window.openModal('modal-correccion');
  }

  campos.tipo.addEventListener('change', aplicarTipo);
  raiz.addEventListener('click', (evento) => {
    const boton = evento.target.closest('[data-corregir]');
    if (boton) abrir(boton);
  });
  form.addEventListener('submit', (evento) => {
    if (!form.checkValidity()) {
      evento.preventDefault();
      form.reportValidity();
    }
  });
})();
