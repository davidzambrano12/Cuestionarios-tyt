/**
 * Períodos académicos: un único cuadro para crear o editar.
 * Datos: #periodos[data-url-editar] (con 0 como id de plantilla) y los
 * atributos data-* de cada botón «Editar».
 */
(function () {
  'use strict';

  const raiz = document.getElementById('periodos');
  const modal = document.getElementById('modal-periodo');
  const form = modal.querySelector('form');
  const ref = (nombre) => modal.querySelector(`[data-ref="${nombre}"]`);
  const campos = {
    anio: form.elements.anio,
    numero: form.elements.numero,
    inicio: form.elements.fecha_inicio,
    fin: form.elements.fecha_fin,
  };

  function abrir({ titulo, accion, boton, datos = null, enUso = false }) {
    form.reset();
    form.action = accion;
    ref('titulo').textContent = titulo;
    ref('guardar').textContent = boton;
    ref('nota').hidden = !enUso;
    if (datos) {
      campos.anio.value = datos.anio;
      campos.numero.value = datos.numero;
      campos.inicio.value = datos.inicio;
      campos.fin.value = datos.fin;
    }
    // Con historial, el año y el número no se cambian (el servidor también los ignora)
    campos.anio.readOnly = enUso;
    campos.numero.readOnly = enUso;
    window.openModal('modal-periodo');
  }

  raiz.addEventListener('click', (evento) => {
    if (evento.target.closest('[data-nuevo-periodo]')) {
      abrir({ titulo: 'Nuevo período académico', accion: form.dataset.urlCrear, boton: 'Crear período' });
      return;
    }
    const editar = evento.target.closest('[data-editar-periodo]');
    if (editar) {
      const d = editar.dataset;
      abrir({
        titulo: `Editar el período ${d.nombre}`,
        accion: raiz.dataset.urlEditar.replace('/0/', `/${d.editarPeriodo}/`),
        boton: 'Guardar cambios',
        datos: d,
        enUso: Boolean(d.enUso),
      });
    }
  });
})();
