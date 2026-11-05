/**
 * Inicio de sesión: obtiene el JWT por la API y luego envía el formulario
 * para crear también la sesión de Django.
 * Datos: #form-login[data-url-token].
 */
(function () {
  'use strict';

  const form = document.getElementById('form-login');
  const enviar = form.querySelector('[data-ref="enviar"]');
  const caja = document.getElementById('login-error');
  const clave = document.getElementById('password');
  let validado = false;
  const bienvenida = document.getElementById('bienvenida-acceso');
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Lo justo para que el saludo se alcance a leer; no se suma a la carga del panel
  const VISIBLE_MINIMO_MS = sinMovimiento ? 0 : 450;
  const DESTINOS = {
    admin: 'Abriendo el panel de administración…',
    docente: 'Abriendo tu panel docente…',
    docente_evaluador: 'Abriendo tu panel docente…',
  };

  function mostrarBienvenida(usuario) {
    const nombre = (usuario && usuario.full_name ? usuario.full_name : '').split(' ')[0];
    bienvenida.querySelector('[data-ref="saludo"]').textContent = nombre ? `Hola, ${nombre}` : 'Hola';
    bienvenida.querySelector('[data-ref="destino"]').textContent =
      DESTINOS[usuario && usuario.rol] || 'Abriendo tus simulacros…';
    bienvenida.hidden = false;
    // En el siguiente cuadro, para que la transición de entrada se ejecute
    requestAnimationFrame(() => bienvenida.classList.add('bienvenida-acceso--visible'));
  }

  // Volver con «Atrás» desde el panel: la página sale de la caché del navegador
  window.addEventListener('pageshow', (evento) => {
    if (!evento.persisted) return;
    bienvenida.hidden = true;
    bienvenida.classList.remove('bienvenida-acceso--visible');
    validado = false;
    enviar.disabled = false;
    enviar.textContent = 'Iniciar sesión';
  });

  function mostrarError(mensaje) {
    caja.textContent = mensaje;
    caja.hidden = false;
    enviar.disabled = false;
    enviar.textContent = 'Iniciar sesión';
  }

  form.addEventListener('submit', async (evento) => {
    if (validado) return; // segunda pasada: envío normal del formulario
    evento.preventDefault();
    caja.hidden = true;
    enviar.disabled = true;
    enviar.textContent = 'Validando…';

    try {
      const respuesta = await fetch(form.dataset.urlToken, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: form.elements.username.value.trim(), password: clave.value }),
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        mostrarError('Usuario o contraseña incorrectos, o la cuenta está suspendida.');
        return;
      }
      localStorage.setItem('access_token', datos.access);
      localStorage.setItem('refresh_token', datos.refresh);
      localStorage.setItem('user_data', JSON.stringify(datos.user));
      validado = true;
      mostrarBienvenida(datos.user);
      setTimeout(() => form.submit(), VISIBLE_MINIMO_MS);
    } catch (error) {
      mostrarError('No hay conexión con el servidor. Intenta de nuevo.');
    }
  });

  form.querySelector('[data-accion="ver-clave"]').addEventListener('click', (evento) => {
    const boton = evento.currentTarget;
    const visible = clave.type === 'password';
    clave.type = visible ? 'text' : 'password';
    boton.setAttribute('aria-pressed', String(visible));
    boton.setAttribute('aria-label', visible ? 'Ocultar contraseña' : 'Mostrar contraseña');
  });

  // Accesos de demostración (solo se renderizan en desarrollo)
  document.querySelectorAll('[data-demo-usuario]').forEach((boton) => {
    boton.addEventListener('click', () => {
      form.elements.username.value = boton.dataset.demoUsuario;
      clave.value = boton.dataset.demoClave;
      form.requestSubmit();
    });
  });
})();
