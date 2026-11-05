/**
 * Banco de preguntas: filtros, y un único modal para crear o editar.
 * Datos: #banco[data-url-crear] y #banco[data-url-editar] (con id 0 de plantilla).
 * Abre el modal automáticamente con #nueva o ?editar=<id> en la URL.
 */
(function () {
  'use strict';

  const raiz = document.getElementById('banco');
  const form = document.getElementById('form-pregunta');
  const modal = document.getElementById('modal-pregunta');
  const titulo = document.getElementById('modal-pregunta-titulo');
  const subtitulo = modal.querySelector('[data-ref="subtitulo"]');
  const botonGuardar = modal.querySelector('[data-ref="guardar"]');
  const campoTipo = document.getElementById('campo-tipo');
  const urlEditar = (id) => raiz.dataset.urlEditar.replace('/0/', `/${id}/`);

  /* ------------------------------------------------------------ Modal */

  // Solo el bloque de opciones del tipo elegido se valida y se envía
  function aplicarTipo(tipo) {
    form.querySelectorAll('fieldset[data-tipo]').forEach((bloque) => {
      const activo = bloque.dataset.tipo === tipo;
      bloque.disabled = !activo;
      bloque.hidden = !activo;
    });
  }

  function abrirNueva() {
    form.reset();
    form.action = raiz.dataset.urlCrear;
    titulo.textContent = 'Nueva pregunta';
    subtitulo.textContent = '';
    botonGuardar.textContent = 'Guardar pregunta';
    aplicarTipo(campoTipo.value);
    window.openModal('modal-pregunta');
  }

  async function abrirEdicion(id) {
    let datos;
    try {
      const respuesta = await fetch(urlEditar(id), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (!respuesta.ok) throw new Error(respuesta.status);
      datos = await respuesta.json();
    } catch (error) {
      window.mostrarNotificacion('No se pudieron cargar los datos de la pregunta.', 'error', 'Banco de preguntas');
      return;
    }

    form.reset();
    form.action = urlEditar(id);
    titulo.textContent = 'Editar pregunta';
    subtitulo.textContent = `Pregunta Cód. P-${id}`;
    botonGuardar.textContent = 'Guardar cambios';
    form.elements.categoria_id.value = datos.categoria_id;
    campoTipo.value = datos.tipo;
    form.elements.texto_base.value = datos.texto_base;
    form.elements.enunciado.value = datos.enunciado;
    form.elements.puntaje.value = datos.puntaje;
    form.elements.retroalimentacion.value = datos.retroalimentacion;
    aplicarTipo(datos.tipo);

    if (datos.tipo === 'MULTIPLE') {
      datos.opciones.slice(0, 4).forEach((opcion, i) => {
        const letra = 'ABCD'[i];
        document.getElementById(`opcion-${letra}`).value = opcion.texto;
        if (opcion.es_correcta) document.getElementById(`correcta-${letra}`).checked = true;
      });
    } else {
      const verdadera = datos.opciones.find((o) => o.texto.toLowerCase().includes('verdadero'));
      form.querySelector(`[name="correcta_vf"][value="${verdadera && verdadera.es_correcta ? 'V' : 'F'}"]`).checked = true;
    }
    window.openModal('modal-pregunta');
  }

  campoTipo.addEventListener('change', () => aplicarTipo(campoTipo.value));

  /* ------------------------------------------------------------ Filtros */

  const filtroTexto = document.getElementById('filtro-pregunta');
  const filtroCategoria = document.getElementById('filtro-categoria');
  const filtroTipo = document.getElementById('filtro-tipo');
  const tarjetas = [...raiz.querySelectorAll('.pregunta-card')];
  const sinResultados = document.getElementById('sin-resultados');
  const contador = document.getElementById('contador-preguntas');

  function filtrar() {
    const texto = filtroTexto.value.toLowerCase().trim();
    const categoria = filtroCategoria.value;
    const tipo = filtroTipo.value;
    let visibles = 0;
    tarjetas.forEach((tarjeta) => {
      const visible = (!texto || tarjeta.dataset.enunciado.includes(texto))
        && (!categoria || tarjeta.dataset.cat === categoria)
        && (!tipo || tarjeta.dataset.tipo === tipo);
      tarjeta.hidden = !visible;
      if (visible) visibles += 1;
    });
    const hayFiltro = Boolean(texto || categoria || tipo);
    sinResultados.hidden = !(tarjetas.length && visibles === 0);
    contador.textContent = hayFiltro ? `Mostrando ${visibles} de ${tarjetas.length} preguntas` : `${tarjetas.length} preguntas`;
  }

  [filtroTexto, filtroCategoria, filtroTipo].forEach((campo) => campo.addEventListener('input', filtrar));

  /* ------------------------------------------------------------ Acciones */

  raiz.addEventListener('click', (evento) => {
    const editar = evento.target.closest('[data-editar]');
    if (editar) { abrirEdicion(editar.dataset.editar); return; }
    if (evento.target.closest('[data-accion="nueva"]')) { abrirNueva(); return; }
    if (evento.target.closest('[data-accion="limpiar-filtros"]')) {
      filtroTexto.value = '';
      filtroCategoria.value = '';
      filtroTipo.value = '';
      filtrar();
    }
  });

  filtrar();
  // Accesos directos desde otras pantallas
  const parametros = new URLSearchParams(location.search);
  if (location.hash === '#nueva') abrirNueva();
  else if (parametros.get('editar')) abrirEdicion(parametros.get('editar'));
})();
