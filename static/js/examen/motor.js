/**
 * Motor común de la sala de examen y de la previsualización docente.
 *
 * Lee las preguntas del <script type="application/json" id="datos-preguntas">
 * (generado con json_script) y pinta la pregunta actual, sus opciones, la
 * barra de progreso y el mapa. No conoce reglas de negocio: avisa de cada
 * selección y del final mediante callbacks, que pone sala.js o
 * previsualizacion.js.
 *
 * Todo el texto que viene del banco de preguntas se inserta con textContent
 * (nunca innerHTML) para que un enunciado importado no pueda inyectar HTML.
 */
(function () {
  'use strict';

  const LETRAS = ['A', 'B', 'C', 'D', 'E'];

  function leerJSON(id, porDefecto) {
    const nodo = document.getElementById(id);
    if (!nodo) return porDefecto;
    try {
      return JSON.parse(nodo.textContent);
    } catch (error) {
      console.error(`No se pudo leer ${id}:`, error);
      return porDefecto;
    }
  }

  function crear(etiqueta, clases, texto) {
    const el = document.createElement(etiqueta);
    if (clases) el.className = clases;
    if (texto !== undefined) el.textContent = texto;
    return el;
  }

  function icono(nombre, clases) {
    const i = document.createElement('i');
    i.setAttribute('data-lucide', nombre);
    if (clases) i.className = clases;
    return i;
  }

  function refrescarIconos(raiz) {
    if (window.lucide) window.lucide.createIcons({ root: raiz });
  }

  class MotorExamen {
    /**
     * @param {HTMLElement} raiz  Elemento #sala-examen.
     * @param {object} opciones
     *   respuestas           {preguntaId: opcionId} iniciales.
     *   textoProgreso(pct)   Texto junto a la barra.
     *   resumenMapa(estado)  Texto bajo el título del mapa.
     *   progreso(estado)     Porcentaje 0-100 que muestra la barra.
     *   decorarOpcion(boton, opcion, pregunta)  Ajustes del modo (p. ej. claves).
     *   alMostrar(pregunta, indice)
     *   alSeleccionar(preguntaId, opcionId)
     *   alTerminar()         Botón "siguiente" en la última pregunta.
     *   textoFinal           Etiqueta del botón en la última pregunta.
     */
    constructor(raiz, opciones = {}) {
      this.raiz = raiz;
      this.op = opciones;
      this.preguntas = leerJSON('datos-preguntas', []);
      this.respuestas = Object.assign({}, opciones.respuestas || {});
      this.indice = 0;
      this.ref = {};
      raiz.querySelectorAll('[data-ref]').forEach((el) => { this.ref[el.dataset.ref] = el; });
      this.btnAnterior = raiz.querySelector('[data-accion="anterior"]');
      this.btnSiguiente = raiz.querySelector('[data-accion="siguiente"]');
    }

    iniciar() {
      if (!this.preguntas.length) {
        this.ref.enunciado.textContent = 'Este cuestionario aún no tiene preguntas vinculadas.';
        this.btnAnterior.hidden = true;
        this.btnSiguiente.hidden = true;
        return;
      }
      this.btnAnterior.addEventListener('click', () => this.ir(this.indice - 1));
      this.btnSiguiente.addEventListener('click', () => {
        if (this.indice >= this.preguntas.length - 1) {
          if (this.op.alTerminar) this.op.alTerminar();
        } else {
          this.ir(this.indice + 1);
        }
      });
      this.construirGrilla();
      this.mostrar(0);
    }

    get actual() { return this.preguntas[this.indice]; }

    get estado() {
      const total = this.preguntas.length;
      const respondidas = this.preguntas.filter((p) => this.respuestas[p.id]).length;
      return { total, respondidas, pendientes: total - respondidas, indice: this.indice };
    }

    ir(indice) {
      if (indice >= 0 && indice < this.preguntas.length) this.mostrar(indice);
    }

    construirGrilla() {
      const grilla = this.ref.grilla;
      grilla.replaceChildren();
      this.preguntas.forEach((p, i) => {
        const btn = crear('button', 'q-nav-item', String(i + 1));
        btn.type = 'button';
        btn.setAttribute('aria-label', `Ir a la pregunta ${i + 1}`);
        btn.addEventListener('click', () => this.ir(i));
        grilla.appendChild(btn);
      });
    }

    seleccionar(opcionId) {
      const pregunta = this.actual;
      this.respuestas[pregunta.id] = opcionId;
      this.mostrar(this.indice);
      if (this.op.alSeleccionar) this.op.alSeleccionar(pregunta.id, opcionId);
    }

    mostrar(indice) {
      this.indice = indice;
      const p = this.actual;
      const ultima = indice === this.preguntas.length - 1;

      this.ref.indice.textContent = String(indice + 1);
      this.ref.competencia.textContent = p.categoria;
      this.ref.puntaje.textContent = `Valor: ${p.puntaje} pt`;
      this.ref.contexto.textContent = p.texto_base || 'Sin contexto adicional. Lee directamente el enunciado.';
      this.ref.enunciado.textContent = p.enunciado;

      this.pintarOpciones(p);

      this.btnAnterior.style.visibility = indice === 0 ? 'hidden' : 'visible';
      this.btnSiguiente.dataset.final = String(ultima);
      this.btnSiguiente.replaceChildren(
        ultima ? icono('check-circle-2', 'icono-16') : crear('span', '', 'Siguiente'),
        ultima ? document.createTextNode(` ${this.op.textoFinal || 'Finalizar'}`) : icono('chevron-right', 'icono-16'),
      );
      refrescarIconos(this.btnSiguiente);

      this.actualizarMapa();
      if (this.op.alMostrar) this.op.alMostrar(p, indice);
    }

    pintarOpciones(p) {
      const contenedor = this.ref.opciones;
      contenedor.replaceChildren();
      p.opciones.forEach((op, i) => {
        const elegida = this.respuestas[p.id] === op.id;
        const boton = crear('button', `option-card${elegida ? ' selected' : ''}`);
        boton.type = 'button';
        boton.setAttribute('role', 'radio');
        boton.setAttribute('aria-checked', String(elegida));

        const texto = crear('span', 'option-card__texto', op.texto);
        const marca = crear('span', 'option-card__marca');
        if (elegida) marca.appendChild(icono('check', 'icono-12'));
        boton.append(crear('span', 'option-letter-badge', LETRAS[i] || String(i + 1)), texto, marca);
        boton.addEventListener('click', () => this.seleccionar(op.id));

        if (this.op.decorarOpcion) this.op.decorarOpcion(boton, op, p);
        contenedor.appendChild(boton);
      });
      refrescarIconos(contenedor);
    }

    actualizarMapa() {
      const botones = this.ref.grilla.children;
      this.preguntas.forEach((p, i) => {
        const btn = botones[i];
        if (!btn) return;
        btn.classList.toggle('answered', Boolean(this.respuestas[p.id]));
        btn.classList.toggle('current', i === this.indice);
        if (i === this.indice) btn.setAttribute('aria-current', 'step');
        else btn.removeAttribute('aria-current');
      });

      const estado = this.estado;
      const pct = this.op.progreso ? this.op.progreso(estado) : Math.round((estado.respondidas / estado.total) * 100);
      this.ref.barra.style.width = `${Math.max(pct, 2)}%`;
      this.ref.porcentaje.textContent = this.op.textoProgreso ? this.op.textoProgreso(pct) : `${pct}% completado`;
      this.ref.resumen.textContent = this.op.resumenMapa
        ? this.op.resumenMapa(estado)
        : `${estado.respondidas} respondidas · ${estado.pendientes} pendientes`;
    }
  }

  window.MotorExamen = MotorExamen;
  window.MotorExamen.leerJSON = leerJSON;
  window.MotorExamen.crear = crear;
  window.MotorExamen.icono = icono;
})();
