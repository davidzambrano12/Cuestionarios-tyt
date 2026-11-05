/**
 * Comportamiento común a todas las páginas (cargado desde layouts/base.html).
 *
 * Interacciones declarativas, sin onclick en el HTML:
 *   <form data-confirmar="¿Seguro?">        pide confirmación antes de enviar
 *   <a data-confirmar="¿Seguro?">            pide confirmación antes de navegar
 *   <button data-abrir-modal="id">          abre el modal #id
 *   <button data-cerrar-modal>              cierra el modal que lo contiene
 *                                           (o data-cerrar-modal="id")
 *   <a data-cerrar-sesion>                  revoca el JWT y cierra la sesión
 *   <a data-ancla-local="seccion">          si ya estás en esa página, desplaza
 *                                           hasta #seccion en vez de recargar
 *   <button data-notificar="texto" data-notificar-titulo="…" data-notificar-tipo="info">
 *
 * API global usada por los scripts de página:
 *   window.mostrarNotificacion(mensaje, tipo, titulo)
 *   window.openModal(id) / window.closeModal(id)
 *   window.csrfToken()
 */
(function () {
  'use strict';

  const DURACION_TOAST_MS = 4500;
  const TITULOS = {
    success: 'Operación exitosa',
    error: 'Atención',
    warning: 'Advertencia',
    info: 'Aviso',
  };
  const ICONOS = { success: 'check-circle-2', error: 'alert-circle', warning: 'alert-triangle', info: 'info' };

  function getCookie(nombre) {
    const par = document.cookie.split(';').map((c) => c.trim()).find((c) => c.startsWith(`${nombre}=`));
    return par ? decodeURIComponent(par.slice(nombre.length + 1)) : null;
  }

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.content) || getCookie('csrftoken') || '';
  }

  function refrescarIconos(raiz) {
    if (window.lucide) window.lucide.createIcons(raiz ? { root: raiz } : undefined);
  }

  /* ---------------------------------------------------------------- Toasts */

  function cerrarToast(toast) {
    if (!toast || toast.classList.contains('toast-closing')) return;
    toast.classList.add('toast-closing');
    setTimeout(() => toast.remove(), 300);
  }

  function programarCierre(toast) {
    setTimeout(() => cerrarToast(toast), DURACION_TOAST_MS);
  }

  function mostrarNotificacion(mensaje, tipo = 'info', titulo = '') {
    const contenedor = document.getElementById('toast-container');
    if (!contenedor) return;
    const clase = TITULOS[tipo] ? tipo : 'info';

    const toast = document.createElement('div');
    toast.className = `toast-item toast-${clase}`;
    toast.setAttribute('role', clase === 'error' ? 'alert' : 'status');

    const caja = document.createElement('div');
    caja.className = 'toast-icon-box';
    const icono = document.createElement('i');
    icono.setAttribute('data-lucide', ICONOS[clase]);
    caja.appendChild(icono);

    const cuerpo = document.createElement('div');
    cuerpo.className = 'toast-content';
    const tituloEl = document.createElement('div');
    tituloEl.className = 'toast-title';
    tituloEl.textContent = titulo || TITULOS[clase];
    const mensajeEl = document.createElement('div');
    mensajeEl.className = 'toast-message';
    mensajeEl.textContent = mensaje;
    cuerpo.append(tituloEl, mensajeEl);

    const cerrar = document.createElement('button');
    cerrar.type = 'button';
    cerrar.className = 'toast-close-btn';
    cerrar.setAttribute('data-cerrar-toast', '');
    cerrar.setAttribute('aria-label', 'Cerrar notificación');
    cerrar.textContent = '×';

    const progreso = document.createElement('div');
    progreso.className = 'toast-progress';
    progreso.style.animationDuration = `${DURACION_TOAST_MS / 1000}s`;

    toast.append(caja, cuerpo, cerrar, progreso);
    contenedor.appendChild(toast);
    refrescarIconos(toast);
    programarCierre(toast);
  }

  /* ---------------------------------------------------------------- Modales */

  function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('open');
    const foco = modal.querySelector('input:not([type=hidden]), select, textarea, button');
    if (foco) setTimeout(() => foco.focus(), 50);
  }

  function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('open');
  }

  /* ---------------------------------------------------------------- Sesión */

  async function cerrarSesion() {
    const cuerpo = document.body.dataset;
    const refresh = localStorage.getItem('refresh_token') || getCookie('refresh_token');
    try {
      if (refresh && cuerpo.urlJwtLogout) {
        await fetch(cuerpo.urlJwtLogout, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify({ refresh }),
        });
      }
    } catch (error) {
      console.error('No se pudo revocar el JWT:', error);
    }
    ['access_token', 'refresh_token', 'user_data'].forEach((k) => localStorage.removeItem(k));
    document.cookie = 'access_token=; path=/; max-age=0;';
    document.cookie = 'refresh_token=; path=/; max-age=0;';
    window.location.href = cuerpo.urlLogout || '/logout/';
  }

  /* ---------------------------------------------------------------- Delegación */

  document.addEventListener('click', (evento) => {
    const el = evento.target.closest(
      '[data-abrir-modal], [data-cerrar-modal], [data-cerrar-toast], [data-cerrar-sesion], a[data-confirmar], [data-ancla-local], [data-notificar]',
    );
    if (!el) return;

    if (el.matches('[data-abrir-modal]')) {
      evento.preventDefault();
      openModal(el.dataset.abrirModal);
    } else if (el.matches('[data-cerrar-modal]')) {
      evento.preventDefault();
      const id = el.dataset.cerrarModal;
      if (id) closeModal(id);
      else el.closest('.modal-backdrop')?.classList.remove('open');
    } else if (el.matches('[data-cerrar-toast]')) {
      cerrarToast(el.closest('.toast-item'));
    } else if (el.matches('[data-cerrar-sesion]')) {
      evento.preventDefault();
      cerrarSesion();
    } else if (el.matches('a[data-confirmar]')) {
      if (!window.confirm(el.dataset.confirmar)) evento.preventDefault();
    } else if (el.matches('[data-ancla-local]')) {
      const destino = document.getElementById(el.dataset.anclaLocal);
      if (destino && new URL(el.href, location.href).pathname === location.pathname) {
        evento.preventDefault();
        destino.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', `#${el.dataset.anclaLocal}`);
      }
    } else if (el.matches('[data-notificar]')) {
      evento.preventDefault();
      mostrarNotificacion(el.dataset.notificar, el.dataset.notificarTipo || 'info', el.dataset.notificarTitulo || '');
    }
  });

  document.addEventListener('submit', (evento) => {
    const form = evento.target;
    if (form.matches('form[data-confirmar]') && !window.confirm(form.dataset.confirmar)) {
      evento.preventDefault();
    }
  });

  // Cerrar el modal abierto con Escape o al hacer clic en el fondo
  document.addEventListener('keydown', (evento) => {
    if (evento.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.open').forEach((m) => m.classList.remove('open'));
    }
  });
  document.addEventListener('mousedown', (evento) => {
    if (evento.target.classList && evento.target.classList.contains('modal-backdrop')) {
      evento.target.classList.remove('open');
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('#toast-container .toast-item').forEach(programarCierre);
    refrescarIconos();
  });

  window.mostrarNotificacion = mostrarNotificacion;
  window.openModal = openModal;
  window.closeModal = closeModal;
  window.csrfToken = csrfToken;
  window.getCookie = getCookie;
})();
