/**
 * Editor de cuestionarios en tres pasos: navegación, validación, ficha
 * resumen en vivo y selección de preguntas del banco.
 *
 * El formulario usa novalidate: este script valida al enviar y, si un campo
 * obligatorio está en un paso oculto, muestra ese paso y lo señala (sin esto
 * el navegador bloquea el envío en silencio).
 */
(function () {
  'use strict';

  const raiz = document.getElementById('configurar-cuestionario');
  const form = document.getElementById('form-cuestionario');
  const ref = (nombre, base = document) => base.querySelector(`[data-ref="${nombre}"]`);
  const pasos = [...raiz.querySelectorAll('section[data-paso]')];
  const botonesPaso = [...raiz.querySelectorAll('.pasos__boton')];
  const lista = ref('lista', raiz);
  const vacio = ref('vacio', raiz);
  const plantilla = document.getElementById('plantilla-pregunta-asignada');
  const modal = document.getElementById('modal-selector-preguntas');

  /* ------------------------------------------------------------ Pasos */

  function mostrarPaso(numero) {
    pasos.forEach((seccion) => { seccion.hidden = seccion.dataset.paso !== String(numero); });
    botonesPaso.forEach((boton) => {
      if (boton.dataset.irPaso === String(numero)) boton.setAttribute('aria-current', 'step');
      else boton.removeAttribute('aria-current');
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function primerInvalido(seccion) {
    return [...seccion.querySelectorAll('input, textarea, select')].find((campo) => !campo.checkValidity());
  }

  function irAPaso(numero) {
    // No avanzar dejando campos obligatorios vacíos en el paso actual
    const actual = pasos.find((s) => !s.hidden);
    if (actual && Number(numero) > Number(actual.dataset.paso)) {
      const campo = primerInvalido(actual);
      if (campo) { campo.reportValidity(); return; }
    }
    mostrarPaso(numero);
  }

  // Las pestañas navegan libremente; "Continuar" valida el paso actual
  raiz.addEventListener('click', (evento) => {
    const boton = evento.target.closest('[data-ir-paso]');
    if (!boton) return;
    if (boton.classList.contains('pasos__boton')) mostrarPaso(boton.dataset.irPaso);
    else irAPaso(boton.dataset.irPaso);
  });

  form.addEventListener('submit', (evento) => {
    for (const seccion of pasos) {
      const campo = primerInvalido(seccion);
      if (campo) {
        evento.preventDefault();
        mostrarPaso(seccion.dataset.paso);
        setTimeout(() => campo.reportValidity(), 300);
        return;
      }
    }
    const apertura = form.elements.fecha_apertura.value;
    const cierre = form.elements.fecha_cierre.value;
    if (apertura && cierre && cierre <= apertura) {
      evento.preventDefault();
      mostrarPaso(1);
      window.mostrarNotificacion('La fecha de cierre debe ser posterior a la de apertura.', 'error', 'Revisa las fechas');
      return;
    }
    const maxima = Number(form.elements.calificacion_maxima.value);
    const aprobacion = Number(form.elements.calificacion_aprobacion.value);
    if (aprobacion > maxima) {
      evento.preventDefault();
      mostrarPaso(2);
      window.mostrarNotificacion('La nota para aprobar no puede superar la calificación máxima.', 'error', 'Revisa la escala');
      return;
    }
    if (evento.submitter && evento.submitter.value === 'publicar' && !lista.children.length) {
      evento.preventDefault();
      mostrarPaso(3);
      window.mostrarNotificacion('Agrega al menos una pregunta antes de publicar.', 'error', 'Cuestionario sin preguntas');
    }
  });

  /* ------------------------------------------------------------ Ficha resumen */

  function formatoFecha(valor) {
    return valor ? valor.replace('T', ' ') : '';
  }

  function actualizarResumen() {
    const minutos = Number(form.elements.tiempo_limite_minutos.value) || 0;
    ref('r-nombre').textContent = form.elements.nombre.value.trim() || 'Sin nombre';
    ref('r-tiempo').textContent = `${minutos} min`;
    ref('tiempo-horas').textContent = minutos ? `Equivale a ${(minutos / 60).toLocaleString('es-CO', { maximumFractionDigits: 1 })} h` : '';
    const maxima = Number(form.elements.calificacion_maxima.value);
    ref('r-escala').textContent = maxima ? maxima.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
    const apertura = form.elements.fecha_apertura.value;
    const cierre = form.elements.fecha_cierre.value;
    ref('r-fechas').textContent = apertura && cierre ? `${formatoFecha(apertura)} → ${formatoFecha(cierre)}` : 'Define las fechas en el paso 1';
  }

  form.addEventListener('input', actualizarResumen);

  /* ------------------------------------------------------------ Preguntas asignadas */

  function recalcular() {
    const items = [...lista.children];
    let total = 0;
    items.forEach((item, i) => {
      total += Number(item.dataset.puntaje) || 0;
      ref('indice', item).textContent = String(i + 1);
    });
    const puntaje = total.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    ['conteo', 'conteo-pestana', 'r-preguntas'].forEach((n) => { ref(n).textContent = String(items.length); });
    ['puntaje', 'r-puntaje'].forEach((n) => { ref(n).textContent = puntaje; });
    vacio.hidden = items.length > 0;
  }

  function crearAsignada(casilla) {
    const item = plantilla.content.firstElementChild.cloneNode(true);
    item.dataset.id = casilla.value;
    item.dataset.puntaje = casilla.dataset.puntaje;
    item.querySelector('input[name="preguntas_ids"]').value = casilla.value;
    ref('categoria', item).textContent = casilla.dataset.categoria;
    ref('tipo', item).textContent = casilla.dataset.tipo;
    ref('valor', item).textContent = casilla.dataset.puntaje;
    ref('enunciado', item).textContent = casilla.dataset.enunciado;
    return item;
  }

  lista.addEventListener('click', (evento) => {
    const quitar = evento.target.closest('[data-quitar]');
    if (!quitar) return;
    quitar.closest('.pregunta-asignada').remove();
    recalcular();
  });

  /* ------------------------------------------------------------ Selector del banco */

  const casillas = [...modal.querySelectorAll('.selector-item__casilla')];
  const contadorSeleccion = ref('seleccionadas', modal);

  function actualizarSeleccion() {
    const n = casillas.filter((c) => c.checked).length;
    contadorSeleccion.textContent = `${n} seleccionada${n === 1 ? '' : 's'}`;
  }

  // Al abrir el selector, las preguntas ya asignadas aparecen deshabilitadas
  raiz.addEventListener('click', (evento) => {
    if (!evento.target.closest('[data-abrir-modal="modal-selector-preguntas"]')) return;
    const asignadas = new Set([...lista.children].map((item) => item.dataset.id));
    casillas.forEach((c) => {
      const yaEsta = asignadas.has(c.value);
      c.disabled = yaEsta;
      c.checked = false;
      c.closest('.selector-item').classList.toggle('selector-item--asignada', yaEsta);
    });
    actualizarSeleccion();
  });

  modal.addEventListener('change', actualizarSeleccion);
  document.getElementById('filtro-selector').addEventListener('input', (evento) => {
    const q = evento.target.value.toLowerCase().trim();
    modal.querySelectorAll('.selector-item').forEach((item) => { item.hidden = !item.dataset.texto.includes(q); });
  });

  modal.querySelector('[data-accion="agregar"]').addEventListener('click', () => {
    casillas.filter((c) => c.checked && !c.disabled).forEach((c) => lista.appendChild(crearAsignada(c)));
    if (window.lucide) window.lucide.createIcons({ root: lista });
    window.closeModal('modal-selector-preguntas');
    recalcular();
  });

  actualizarResumen();
  recalcular();
})();
