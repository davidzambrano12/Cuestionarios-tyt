/**
 * Previsualización docente: recorre el examen sin registrar intentos y
 * permite revelar la clave correcta y la retroalimentación.
 * Datos desde la plantilla:
 *   #sala-examen[data-url-salir]           a dónde ir al terminar
 *   #sala-examen[data-url-editar-pregunta] URL del banco con __ID__ como marcador
 */
(function () {
  'use strict';

  const raiz = document.getElementById('sala-examen');
  const { crear, icono } = window.MotorExamen;
  const btnClaves = document.querySelector('[data-accion="claves"]');
  const panelRetro = document.querySelector('[data-ref="retroalimentacion"]');
  const textoRetro = document.querySelector('[data-ref="texto-retroalimentacion"]');
  const linkEditar = document.querySelector('[data-ref="editar-pregunta"]');
  let mostrarClaves = false;

  const motor = new window.MotorExamen(raiz, {
    textoFinal: 'Fin de la previsualización',
    progreso: (estado) => Math.round(((estado.indice + 1) / estado.total) * 100),
    textoProgreso: (pct) => `${pct}% explorado`,
    resumenMapa: (estado) => `Pregunta ${estado.indice + 1} de ${estado.total}`,
    alTerminar: () => { window.location.href = raiz.dataset.urlSalir; },
    decorarOpcion(boton, opcion) {
      if (!mostrarClaves || !opcion.es_correcta) return;
      boton.classList.add('es-clave');
      const etiqueta = crear('span', 'badge badge-success ml-2');
      etiqueta.append(icono('check', 'icono-12'), document.createTextNode(' Clave correcta'));
      boton.querySelector('.option-card__texto').appendChild(etiqueta);
    },
    alMostrar(pregunta) {
      linkEditar.href = raiz.dataset.urlEditarPregunta.replace('__ID__', pregunta.id);
      panelRetro.hidden = !mostrarClaves;
      textoRetro.textContent = pregunta.retroalimentacion
        || 'El autor no registró una retroalimentación para esta pregunta.';
    },
  });

  btnClaves.addEventListener('click', () => {
    mostrarClaves = !mostrarClaves;
    btnClaves.setAttribute('aria-pressed', String(mostrarClaves));
    btnClaves.querySelector('[data-ref="texto-claves"]').textContent = mostrarClaves
      ? 'Ocultar claves'
      : 'Revelar claves y retroalimentación';
    motor.mostrar(motor.indice);
  });

  motor.iniciar();
})();
