/**
 * Revisión de la importación: abre el modal de corrección con los datos de
 * la fila (atributo data-fila, JSON escapado por la plantilla) y ajusta las
 * opciones según el tipo. Todo el texto del Excel se asigna con value o
 * textContent, nunca como HTML.
 */
(function () {
  'use strict';

  const raiz = document.getElementById('revision-importacion');
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
