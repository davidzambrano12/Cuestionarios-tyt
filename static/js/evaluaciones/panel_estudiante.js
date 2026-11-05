/**
 * Panel del estudiante: pestañas Disponibles / Programados / Mis intentos,
 * accesos directos [data-ir-pestana] y desplazamiento con #cuestionarios.
 */
(function () {
  'use strict';

  const raiz = document.getElementById('panel-estudiante');
  const pestanas = [...raiz.querySelectorAll('[role="tab"]')];
  const seccion = document.getElementById('cuestionarios');

  function mostrar(nombre, { enfocar = false, desplazar = false } = {}) {
    pestanas.forEach((tab) => {
      const activa = tab.dataset.pestana === nombre;
      tab.classList.toggle('active', activa);
      tab.setAttribute('aria-selected', String(activa));
      tab.tabIndex = activa ? 0 : -1;
      document.getElementById(`pestana-${tab.dataset.pestana}`).hidden = !activa;
      if (activa && enfocar) tab.focus();
    });
    if (desplazar) seccion.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  raiz.addEventListener('click', (evento) => {
    const tab = evento.target.closest('[role="tab"]');
    if (tab) { mostrar(tab.dataset.pestana); return; }
    const atajo = evento.target.closest('[data-ir-pestana]');
    if (atajo) mostrar(atajo.dataset.irPestana, { desplazar: true });
  });

  raiz.querySelector('[role="tablist"]').addEventListener('keydown', (evento) => {
    if (evento.key !== 'ArrowRight' && evento.key !== 'ArrowLeft') return;
    const actual = pestanas.findIndex((t) => t.getAttribute('aria-selected') === 'true');
    const paso = evento.key === 'ArrowRight' ? 1 : -1;
    mostrar(pestanas[(actual + paso + pestanas.length) % pestanas.length].dataset.pestana, { enfocar: true });
  });

  if (location.hash === '#cuestionarios') {
    setTimeout(() => seccion.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
  }
})();
