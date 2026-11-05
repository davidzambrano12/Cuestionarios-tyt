/**
 * Sala de examen del estudiante: autoguardado, temporizador y entrega.
 * Datos desde la plantilla:
 *   #sala-examen[data-url-guardar]       endpoint de autoguardado
 *   #sala-examen[data-segundos-restantes] tiempo validado por el servidor
 *   #sala-examen[data-segundos-limite]    tiempo total del cuestionario
 *   #datos-respuestas                     respuestas guardadas (json_script)
 */
(function () {
  'use strict';

  const raiz = document.getElementById('sala-examen');
  const form = document.getElementById('form-evaluacion');
  const campoRespuestas = document.getElementById('datos-respuestas-json');
  const indicadorGuardado = document.querySelector('[data-ref="guardado"]');
  const urlGuardar = raiz.dataset.urlGuardar;
  const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;

  const motor = new window.MotorExamen(raiz, {
    respuestas: window.MotorExamen.leerJSON('datos-respuestas', {}),
    textoFinal: 'Finalizar y entregar',
    alSeleccionar: guardar,
    alTerminar: confirmarEntrega,
  });

  function sincronizarCampo() {
    campoRespuestas.value = JSON.stringify(motor.respuestas);
  }

  function marcarGuardado(texto, estado) {
    if (!indicadorGuardado) return;
    indicadorGuardado.textContent = texto;
    indicadorGuardado.dataset.estado = estado;
  }

  // Autoguardado asíncrono no intrusivo (RULE-03 §3.1)
  async function guardar(preguntaId, opcionId) {
    sincronizarCampo();
    marcarGuardado('Guardando…', 'guardando');
    try {
      const respuesta = await fetch(urlGuardar, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ pregunta_id: preguntaId, opcion_id: opcionId }),
      });
      const datos = await respuesta.json();
      if (datos.status === 'ok') marcarGuardado('Guardado', 'ok');
      else marcarGuardado('No se pudo guardar', 'error');
    } catch (error) {
      // La respuesta sigue en el formulario: se enviará al entregar
      marcarGuardado('Sin conexión: se guardará al entregar', 'error');
    }
  }

  function entregar() {
    sincronizarCampo();
    const boton = raiz.querySelector('[data-accion="siguiente"]');
    boton.disabled = true;
    boton.textContent = 'Enviando y calificando…';
    form.submit();
  }

  function confirmarEntrega() {
    const { total, respondidas, pendientes } = motor.estado;
    const mensaje = [`Respondiste ${respondidas} de ${total} preguntas.`];
    if (pendientes > 0) {
      mensaje.push(`Te ${pendientes === 1 ? 'falta 1 pregunta' : `faltan ${pendientes} preguntas`}: se calificarán con 0 puntos.`);
    }
    mensaje.push('Después de entregar no podrás cambiar tus respuestas.');
    window.confirmar({
      titulo: '¿Entregar tu examen?',
      mensaje: mensaje.join('\n'),
      boton: 'Entregar examen',
      cancelar: 'Volver al examen',
      tipo: pendientes > 0 ? 'aviso' : 'primario',
    }).then((aceptado) => {
      if (aceptado) entregar();
    });
  }

  // Temporizador regresivo con alertas progresivas (RULE-03 §2.3)
  function iniciarTemporizador() {
    const reloj = document.querySelector('[data-ref="reloj"]');
    const caja = reloj.closest('.eval-timer-box');
    const limite = Number(raiz.dataset.segundosLimite) || 0;
    let restantes = Number(raiz.dataset.segundosRestantes) || 0;

    const pintar = () => {
      const h = String(Math.floor(restantes / 3600)).padStart(2, '0');
      const m = String(Math.floor((restantes % 3600) / 60)).padStart(2, '0');
      const s = String(restantes % 60).padStart(2, '0');
      reloj.textContent = `${h}:${m}:${s}`;
      if (restantes < 120) caja.dataset.estado = 'critico';
      else if (restantes < 300 || restantes < limite * 0.1) caja.dataset.estado = 'aviso';
      else delete caja.dataset.estado;
    };

    pintar();
    const intervalo = setInterval(() => {
      restantes -= 1;
      if (restantes <= 0) {
        clearInterval(intervalo);
        restantes = 0;
        pintar();
        window.mostrarNotificacion('El tiempo límite terminó. Tu intento se enviará automáticamente.', 'warning', 'Tiempo agotado');
        setTimeout(entregar, 1200);
        return;
      }
      pintar();
    }, 1000);
  }

  document.querySelector('[data-accion="sincronizacion"]').addEventListener('click', () => {
    window.mostrarNotificacion('El temporizador sigue corriendo en el servidor aunque salgas de la página.', 'info', 'Sincronización');
  });
  document.querySelector('[data-accion="entregar"]').addEventListener('click', confirmarEntrega);
  document.querySelector('[data-confirmar-salida]').addEventListener('click', (evento) => {
    evento.preventDefault();
    const destino = evento.currentTarget.href;
    window.confirmar({
      titulo: '¿Salir de la sala de examen?',
      mensaje: 'El temporizador seguirá corriendo aunque salgas.\nLas respuestas ya guardadas se conservan y podrás volver mientras quede tiempo.',
      boton: 'Salir de la sala',
      cancelar: 'Seguir en el examen',
      tipo: 'aviso',
    }).then((aceptado) => {
      if (aceptado) window.location.href = destino;
    });
  });

  sincronizarCampo();
  motor.iniciar();
  iniciarTemporizador();
})();
