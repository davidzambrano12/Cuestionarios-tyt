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
      form.submit();
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
