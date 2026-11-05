/**
 * Cursos y matrículas.
 *   - Listado: aplicar el período al elegirlo.
 *   - Detalle: filtrar estudiantes (texto y «con / sin intentos»).
 *   - Matricular: buscar en vivo o pegar una lista de códigos; los elegidos se
 *     acumulan como etiquetas y se envían juntos. Todo el texto que llega del
 *     servidor se inserta con textContent.
 */
(function () {
  'use strict';

  document.querySelectorAll('[data-enviar-al-cambiar]').forEach((select) => {
    select.addEventListener('change', () => select.form.submit());
  });

  const normalizar = (t) => (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

  function crear(etiqueta, clase, texto) {
    const el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto !== undefined) el.textContent = texto;
    return el;
  }

  /* ------------------------------------------------------------ Lista del curso */

  const filtro = document.getElementById('filtro-matriculados');
  const filas = Array.from(document.querySelectorAll('.fila-matricula'));
  const botonesResumen = Array.from(document.querySelectorAll('[data-filtro-matricula]'));
  let filtroIntentos = 'todos';

  function filtrarLista() {
    const q = normalizar(filtro ? filtro.value.trim() : '');
    let visibles = 0;
    filas.forEach((fila) => {
      const ok = (!q || normalizar(fila.dataset.texto).includes(q))
        && (filtroIntentos === 'todos' || fila.dataset.intentos === filtroIntentos);
      fila.hidden = !ok;
      if (ok) visibles += 1;
    });
    const vacio = document.querySelector('[data-ref="sin-coincidencias"]');
    if (vacio) vacio.hidden = visibles > 0;
  }
  if (filtro) filtro.addEventListener('input', filtrarLista);
  botonesResumen.forEach((boton) => boton.addEventListener('click', () => {
    filtroIntentos = boton.dataset.filtroMatricula;
    botonesResumen.forEach((b) => {
      b.classList.toggle('active', b === boton);
      b.setAttribute('aria-pressed', String(b === boton));
    });
    filtrarLista();
  }));

  /* ------------------------------------------------------------ Matricular */

  const modal = document.getElementById('modal-matricular');
  if (!modal) return;

  const ref = (nombre) => modal.querySelector(`[data-ref="${nombre}"]`);
  const seleccion = new Map(); // id → {id, nombre, codigo, otro_curso}
  const buscador = document.getElementById('buscar-estudiante');
  const textarea = document.getElementById('codigos');

  function pintarSeleccion() {
    const lista = ref('seleccionados');
    const ocultos = ref('ocultos');
    lista.replaceChildren();
    ocultos.replaceChildren();
    seleccion.forEach((est) => {
      const chip = crear('li', 'chip-estudiante');
      chip.append(crear('span', '', est.nombre));
      const quitar = crear('button', 'chip-estudiante__quitar', '×');
      quitar.type = 'button';
      quitar.setAttribute('aria-label', `Quitar a ${est.nombre}`);
      quitar.addEventListener('click', () => { seleccion.delete(est.id); pintarSeleccion(); sincronizarCasillas(); });
      chip.append(quitar);
      lista.append(chip);
      const oculto = crear('input');
      oculto.type = 'hidden';
      oculto.name = 'estudiantes';
      oculto.value = est.id;
      ocultos.append(oculto);
    });
    const n = seleccion.size;
    ref('titulo-seleccion').textContent = n
      ? `${n} estudiante${n === 1 ? '' : 's'} seleccionado${n === 1 ? '' : 's'}`
      : 'Ningún estudiante seleccionado';
    ref('matricular').disabled = n === 0;
    ref('matricular-texto').textContent = n ? `Matricular ${n} estudiante${n === 1 ? '' : 's'}` : 'Matricular';
  }

  function sincronizarCasillas() {
    // En la búsqueda y en la lista de códigos revisados
    modal.querySelectorAll('.resultado-estudiante input[type="checkbox"]').forEach((casilla) => {
      casilla.checked = seleccion.has(Number(casilla.value));
    });
  }

  function filaEstudiante(est) {
    const li = crear('li');
    const label = crear('label', 'resultado-estudiante');
    const casilla = crear('input');
    casilla.type = 'checkbox';
    casilla.value = est.id;
    casilla.className = 'form-check';
    casilla.checked = seleccion.has(est.id);
    casilla.addEventListener('change', () => {
      if (casilla.checked) seleccion.set(est.id, est);
      else seleccion.delete(est.id);
      pintarSeleccion();
    });
    const avatar = crear('span', 'avatar-inicial', (est.nombre || '?').charAt(0).toUpperCase());
    avatar.setAttribute('aria-hidden', 'true');
    const datos = crear('span', 'resultado-estudiante__datos');
    datos.append(crear('span', 'peso-semibold', est.nombre), crear('span', 'texto-xs texto-suave', est.codigo));
    if (est.otro_curso) {
      datos.append(crear('span', 'texto-xs texto-aviso', `Ya está en ${est.otro_curso} este período`));
    }
    label.append(casilla, avatar, datos);
    li.append(label);
    return li;
  }

  // Búsqueda en vivo: espera a que se deje de escribir para no consultar en cada tecla
  let espera = null;
  let ultimaConsulta = 0;
  async function buscar() {
    const q = buscador.value.trim();
    const estado = ref('estado-busqueda');
    const resultados = ref('resultados');
    if (q.length < 2) {
      resultados.replaceChildren();
      estado.textContent = 'Escribe al menos 2 letras. Solo aparecen estudiantes activos que no están en este curso.';
      return;
    }
    const consulta = ++ultimaConsulta;
    estado.textContent = 'Buscando…';
    try {
      const respuesta = await fetch(`${modal.dataset.urlBuscar}?q=${encodeURIComponent(q)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const datos = await respuesta.json();
      if (consulta !== ultimaConsulta) return; // llegó una búsqueda más nueva
      resultados.replaceChildren(...datos.resultados.map(filaEstudiante));
      estado.textContent = datos.resultados.length
        ? `${datos.resultados.length}${datos.mas ? '+' : ''} resultado${datos.resultados.length === 1 ? '' : 's'}${datos.mas ? ': escribe más para afinar' : ''}`
        : `Ningún estudiante sin matricular coincide con «${q}».`;
    } catch (error) {
      estado.textContent = 'No se pudo buscar. Revisa la conexión e intenta de nuevo.';
    }
  }
  buscador.addEventListener('input', () => {
    clearTimeout(espera);
    espera = setTimeout(buscar, 250);
  });
  buscador.addEventListener('keydown', (evento) => {
    if (evento.key === 'Enter') { evento.preventDefault(); clearTimeout(espera); buscar(); }
  });

  // Lista de códigos pegada
  function bloque(titulo, clase, elementos) {
    const div = crear('div', `revision-bloque ${clase}`);
    div.append(crear('p', 'revision-bloque__titulo', titulo));
    if (elementos) div.append(elementos);
    return div;
  }

  modal.querySelector('[data-accion="revisar-codigos"]').addEventListener('click', async (evento) => {
    const boton = evento.currentTarget;
    const revision = ref('revision');
    if (!textarea.value.trim()) {
      textarea.focus();
      return;
    }
    boton.disabled = true;
    try {
      const cuerpo = new FormData();
      cuerpo.append('codigos', textarea.value);
      const respuesta = await fetch(modal.dataset.urlRevisar, {
        method: 'POST', body: cuerpo, headers: { 'X-CSRFToken': window.csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
      });
      const datos = await respuesta.json();
      revision.hidden = false;
      if (!respuesta.ok) {
        revision.replaceChildren(bloque(datos.detail || 'No se pudo revisar la lista.', 'revision-bloque--error'));
        return;
      }
      datos.encontrados.forEach((est) => seleccion.set(est.id, est));
      pintarSeleccion();
      // Primero lo que necesita atención, para que no quede oculto al final
      const partes = [];
      if (datos.no_existen.length) {
        partes.push(bloque(`${datos.no_existen.length} no corresponde${datos.no_existen.length === 1 ? '' : 'n'} a ningún estudiante activo: ${datos.no_existen.join(', ')}`, 'revision-bloque--error'));
      }
      if (datos.ya_matriculados.length) {
        partes.push(bloque(`${datos.ya_matriculados.length} ya estaba${datos.ya_matriculados.length === 1 ? '' : 'n'} en el curso: ${datos.ya_matriculados.join(', ')}`, 'revision-bloque--info'));
      }
      if (datos.encontrados.length) {
        const ul = crear('ul', 'matricular__resultados');
        datos.encontrados.forEach((est) => ul.append(filaEstudiante(est)));
        partes.push(bloque(`${datos.encontrados.length} encontrado${datos.encontrados.length === 1 ? '' : 's'}: quedan seleccionados abajo`, 'revision-bloque--ok', ul));
      } else if (!partes.length) {
        partes.push(bloque('No se encontró ningún código en el texto pegado.', 'revision-bloque--info'));
      }
      revision.replaceChildren(...partes);
    } catch (error) {
      revision.hidden = false;
      revision.replaceChildren(bloque('No se pudo revisar la lista. Revisa la conexión e intenta de nuevo.', 'revision-bloque--error'));
    } finally {
      boton.disabled = false;
    }
  });

  // Pestañas del cuadro
  const pestanas = Array.from(modal.querySelectorAll('[data-pestana-matricula]'));
  function elegirPestana(pestana, enfocar) {
    pestanas.forEach((p) => {
      const activa = p === pestana;
      p.classList.toggle('active', activa);
      p.setAttribute('aria-selected', String(activa));
      p.tabIndex = activa ? 0 : -1;
      document.getElementById(p.getAttribute('aria-controls')).hidden = !activa;
    });
    if (enfocar) pestana.focus();
    (pestana.dataset.pestanaMatricula === 'buscar' ? buscador : textarea).focus();
  }
  pestanas.forEach((p, i) => {
    p.addEventListener('click', () => elegirPestana(p));
    p.addEventListener('keydown', (evento) => {
      if (evento.key !== 'ArrowRight' && evento.key !== 'ArrowLeft') return;
      const siguiente = pestanas[(i + (evento.key === 'ArrowRight' ? 1 : -1) + pestanas.length) % pestanas.length];
      elegirPestana(siguiente, true);
      siguiente.focus();
    });
  });

  // Al abrir, el cursor queda en el buscador
  document.querySelectorAll('[data-abrir-modal="modal-matricular"]').forEach((boton) => {
    boton.addEventListener('click', () => setTimeout(() => buscador.focus(), 60));
  });

  pintarSeleccion();
})();
