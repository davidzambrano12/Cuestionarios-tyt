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
 *   <button data-alternar-barra>            contrae o expande la barra lateral (se recuerda)
 *   <button data-abrir-barra>               abre la barra lateral en celular
 *   <div data-menu-desplegable>             menú desplegable: un <button aria-controls>
 *                                           y una lista role="menu" con role="menuitem"
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

  /* ---------------------------------------------------------------- Barra lateral */

  const ES_MOVIL = window.matchMedia('(max-width: 767.98px)');
  const ES_MEDIANA = window.matchMedia('(max-width: 1279.98px)');
  const UN_ANIO = 60 * 60 * 24 * 365;

  function contenedorApp() {
    return document.querySelector('.app-container[data-barra]');
  }

  function barraContraida(contenedor) {
    const estado = contenedor.dataset.barra;
    return estado === 'contraida' || (estado === 'auto' && ES_MEDIANA.matches);
  }

  // Mantiene el botón coherente con lo que se ve (en "auto" depende del ancho)
  function sincronizarBarra() {
    const contenedor = contenedorApp();
    const boton = contenedor && contenedor.querySelector('[data-alternar-barra]');
    if (!boton) return;
    const contraida = barraContraida(contenedor);
    boton.setAttribute('aria-expanded', String(!contraida));
    boton.querySelector('.nav-item__texto').textContent = contraida ? 'Expandir menú' : 'Contraer menú';
  }

  function alternarBarra() {
    const contenedor = contenedorApp();
    contenedor.dataset.barra = barraContraida(contenedor) ? 'expandida' : 'contraida';
    document.cookie = `barra_lateral=${contenedor.dataset.barra}; path=/; max-age=${UN_ANIO}; SameSite=Lax`;
    sincronizarBarra();
  }

  // En celular, la barra cerrada está fuera de pantalla: inert la saca del orden de Tab
  function aplicarInertBarra() {
    const contenedor = contenedorApp();
    if (!contenedor) return;
    contenedor.querySelector('.sidebar').inert = ES_MOVIL.matches && !contenedor.classList.contains('barra-abierta');
  }

  function abrirBarraMovil() {
    const contenedor = contenedorApp();
    contenedor.classList.add('barra-abierta');
    contenedor.querySelector('[data-cerrar-barra]').hidden = false;
    contenedor.querySelector('[data-abrir-barra]').setAttribute('aria-expanded', 'true');
    // Primero el foco y después inert: al revés, el foco del botón se pierde en <body>
    aplicarInertBarra();
    const primero = contenedor.querySelector('.sidebar .nav-item');
    if (primero) primero.focus();
    contenedor.querySelector('.main-content').inert = true;
  }

  function cerrarBarraMovil(devolverFoco) {
    const contenedor = contenedorApp();
    if (!contenedor || !contenedor.classList.contains('barra-abierta')) return;
    contenedor.classList.remove('barra-abierta');
    contenedor.querySelector('[data-cerrar-barra]').hidden = true;
    contenedor.querySelector('.main-content').inert = false;
    const boton = contenedor.querySelector('[data-abrir-barra]');
    boton.setAttribute('aria-expanded', 'false');
    if (devolverFoco) boton.focus();
    aplicarInertBarra();
  }

  document.addEventListener('click', (evento) => {
    if (evento.target.closest('[data-alternar-barra]')) alternarBarra();
    else if (evento.target.closest('[data-abrir-barra]')) abrirBarraMovil();
    else if (evento.target.closest('[data-cerrar-barra]')) cerrarBarraMovil(true);
    else if (evento.target.closest('.sidebar .nav-item') && ES_MOVIL.matches) cerrarBarraMovil(false);
  });

  document.addEventListener('keydown', (evento) => {
    if (evento.key === 'Escape') cerrarBarraMovil(true);
  });

  ES_MOVIL.addEventListener('change', () => {
    cerrarBarraMovil(false);
    aplicarInertBarra();
  });
  ES_MEDIANA.addEventListener('change', sincronizarBarra);

  /* ---------------------------------------------------------------- Menús desplegables */

  function itemsDeMenu(menu) {
    return Array.from(menu.querySelectorAll('[role="menuitem"]'));
  }

  function abrirMenu(menu, enfocar) {
    cerrarMenus(menu);
    const boton = menu.querySelector('[aria-haspopup]');
    const lista = menu.querySelector('[role="menu"]');
    boton.setAttribute('aria-expanded', 'true');
    lista.hidden = false;
    const items = itemsDeMenu(menu);
    if (enfocar === 'primero' && items.length) items[0].focus();
    if (enfocar === 'ultimo' && items.length) items[items.length - 1].focus();
  }

  function cerrarMenu(menu, devolverFoco) {
    const boton = menu.querySelector('[aria-haspopup]');
    const lista = menu.querySelector('[role="menu"]');
    if (!lista || lista.hidden) return;
    lista.hidden = true;
    boton.setAttribute('aria-expanded', 'false');
    if (devolverFoco) boton.focus();
  }

  function cerrarMenus(excepto) {
    document.querySelectorAll('[data-menu-desplegable]').forEach((m) => {
      if (m !== excepto) cerrarMenu(m, false);
    });
  }

  document.addEventListener('click', (evento) => {
    const boton = evento.target.closest('[data-menu-desplegable] > [aria-haspopup]');
    if (boton) {
      const menu = boton.closest('[data-menu-desplegable]');
      if (boton.getAttribute('aria-expanded') === 'true') cerrarMenu(menu, false);
      // evento.detail === 0: activado con teclado (Enter/Espacio) → enfocar la primera opción
      else abrirMenu(menu, evento.detail === 0 ? 'primero' : null);
      return;
    }
    if (!evento.target.closest('[data-menu-desplegable]')) cerrarMenus(null);
  });

  document.addEventListener('keydown', (evento) => {
    const menu = evento.target.closest && evento.target.closest('[data-menu-desplegable]');
    if (!menu) return;
    const items = itemsDeMenu(menu);
    const indice = items.indexOf(document.activeElement);
    const enBoton = evento.target.matches('[aria-haspopup]');

    if (evento.key === 'Escape') {
      cerrarMenu(menu, true);
    } else if (evento.key === 'ArrowDown') {
      evento.preventDefault();
      if (enBoton) abrirMenu(menu, 'primero');
      else items[(indice + 1) % items.length].focus();
    } else if (evento.key === 'ArrowUp') {
      evento.preventDefault();
      if (enBoton) abrirMenu(menu, 'ultimo');
      else items[(indice - 1 + items.length) % items.length].focus();
    } else if (evento.key === 'Home' && !enBoton) {
      evento.preventDefault();
      items[0].focus();
    } else if (evento.key === 'End' && !enBoton) {
      evento.preventDefault();
      items[items.length - 1].focus();
    }
  });

  // Al salir con Tab, el menú se cierra
  document.addEventListener('focusout', (evento) => {
    const menu = evento.target.closest && evento.target.closest('[data-menu-desplegable]');
    if (menu && evento.relatedTarget && !menu.contains(evento.relatedTarget)) cerrarMenu(menu, false);
  });

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
    sincronizarBarra();
    aplicarInertBarra();
    refrescarIconos();
  });

  window.mostrarNotificacion = mostrarNotificacion;
  window.openModal = openModal;
  window.closeModal = closeModal;
  window.csrfToken = csrfToken;
  window.getCookie = getCookie;
})();
