/**
 * Resultado de un intento: filtro de la revisión por estado e impresión.
 */
(function () {
  'use strict';

  const raiz = document.getElementById('resultado-intento');
  const chips = [...raiz.querySelectorAll('.chip-filtro')];
  const tarjetas = [...raiz.querySelectorAll('.revision')];

  chips.forEach((chip) => chip.addEventListener('click', () => {
    const filtro = chip.dataset.filtro;
    chips.forEach((c) => {
      const activo = c === chip;
      c.classList.toggle('active', activo);
      c.setAttribute('aria-pressed', String(activo));
    });
    tarjetas.forEach((t) => { t.hidden = filtro !== 'todas' && t.dataset.estado !== filtro; });
  }));

  const imprimir = raiz.querySelector('[data-accion="imprimir"]');
  if (imprimir) imprimir.addEventListener('click', () => window.print());
})();
