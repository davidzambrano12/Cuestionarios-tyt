/**
 * Usuarios y roles: pestañas, búsqueda y filtros combinados, y modales de
 * edición rellenados desde atributos data-* (nunca concatenando texto en JS).
 * Datos: #usuarios-roles[data-url-editar-usuario|data-url-editar-permisos|data-url-permisos-rol]
 * con 0 como id de plantilla.
 */
(function () {
  'use strict';

  const raiz = document.getElementById('usuarios-roles');
  const url = (clave, id) => raiz.dataset[clave].replace('/0/', `/${id}/`);
  const buscador = document.getElementById('filtro-texto');
  const contador = document.getElementById('contador');
  const sinResultados = document.getElementById('sin-resultados');
  const pestanas = [...raiz.querySelectorAll('[data-pestana]')];
  const filtros = { rol: '', estado: '' };
  let pestanaActual = 'usuarios';

  /* ------------------------------------------------------------ Filtros */

  function aplicarFiltros() {
    const panel = document.getElementById(`panel-${pestanaActual}`);
    const tarjetas = [...panel.querySelectorAll('.tarjeta-cuenta')];
    const q = buscador.value.toLowerCase().trim();
    let visibles = 0;
    tarjetas.forEach((tarjeta) => {
      const visible = (!q || tarjeta.dataset.texto.includes(q))
        && (pestanaActual !== 'usuarios' || ((!filtros.rol || tarjeta.dataset.rol === filtros.rol)
          && (!filtros.estado || tarjeta.dataset.estado === filtros.estado)));
      tarjeta.hidden = !visible;
      if (visible) visibles += 1;
    });
    const hayFiltro = q || (pestanaActual === 'usuarios' && (filtros.rol || filtros.estado));
    contador.textContent = hayFiltro ? `Mostrando ${visibles} de ${tarjetas.length}` : '';
    sinResultados.hidden = !(tarjetas.length && visibles === 0);
  }

  function marcarChip(grupo, valor) {
    raiz.querySelectorAll(`[data-filtro-${grupo}]`).forEach((chip) => {
      const activo = chip.dataset[grupo === 'rol' ? 'filtroRol' : 'filtroEstado'] === valor;
      chip.classList.toggle('active', activo);
      chip.setAttribute('aria-pressed', String(activo));
    });
  }

  function cambiarPestana(nombre, enfocar = false) {
    pestanaActual = nombre;
    pestanas.forEach((tab) => {
      const activa = tab.dataset.pestana === nombre;
      tab.classList.toggle('active', activa);
      tab.setAttribute('aria-selected', String(activa));
      tab.tabIndex = activa ? 0 : -1;
      document.getElementById(`panel-${tab.dataset.pestana}`).hidden = !activa;
      if (activa && enfocar) tab.focus();
    });
    raiz.querySelectorAll('[data-solo-pestana]').forEach((el) => { el.hidden = el.dataset.soloPestana !== nombre; });
    buscador.placeholder = nombre === 'usuarios' ? 'Buscar por nombre, código o correo…' : 'Buscar rol por nombre o código…';
    aplicarFiltros();
  }

  pestanas.forEach((tab) => tab.addEventListener('click', () => cambiarPestana(tab.dataset.pestana)));
  raiz.querySelector('[role="tablist"]').addEventListener('keydown', (evento) => {
    if (evento.key === 'ArrowRight' || evento.key === 'ArrowLeft') {
      cambiarPestana(pestanaActual === 'usuarios' ? 'roles' : 'usuarios', true);
    }
  });
  buscador.addEventListener('input', aplicarFiltros);

  /* ------------------------------------------------------------ Modales de edición */

  function editarUsuario(boton) {
    const d = boton.dataset;
    const form = document.getElementById('form-editar-usuario');
    form.reset();
    form.action = url('urlEditarUsuario', d.editarUsuario);
    document.querySelector('[data-ref="subtitulo-usuario"]').textContent = `${d.nombre} ${d.apellido}`.trim();
    form.elements.first_name.value = d.nombre;
    form.elements.last_name.value = d.apellido;
    form.elements.email.value = d.email;
    form.elements.codigo_institucional.value = d.codigo;
    if (d.rol) form.elements.rol_id.value = d.rol;
    window.openModal('modal-editar-usuario');
  }

  async function editarPermisos(boton) {
    const id = boton.dataset.editarPermisos;
    const form = document.getElementById('form-editar-permisos');
    form.action = url('urlEditarPermisos', id);
    document.querySelector('[data-ref="nombre-rol"]').textContent = boton.dataset.nombre;
    form.querySelectorAll('input[type="checkbox"]').forEach((c) => { c.checked = false; });
    try {
      const respuesta = await fetch(url('urlPermisosRol', id));
      if (!respuesta.ok) throw new Error(respuesta.status);
      const datos = await respuesta.json();
      datos.permisos_ids.forEach((pid) => {
        const casilla = document.getElementById(`editar-permiso-${pid}`);
        if (casilla) casilla.checked = true;
      });
    } catch (error) {
      window.mostrarNotificacion('No se pudieron cargar los permisos del rol.', 'error', 'Roles');
      return;
    }
    window.openModal('modal-editar-permisos');
  }

  raiz.addEventListener('click', (evento) => {
    const chipRol = evento.target.closest('[data-filtro-rol]');
    const chipEstado = evento.target.closest('[data-filtro-estado]');
    if (chipRol) { filtros.rol = chipRol.dataset.filtroRol; marcarChip('rol', filtros.rol); aplicarFiltros(); return; }
    if (chipEstado) { filtros.estado = chipEstado.dataset.filtroEstado; marcarChip('estado', filtros.estado); aplicarFiltros(); return; }

    const usuario = evento.target.closest('[data-editar-usuario]');
    if (usuario) { editarUsuario(usuario); return; }
    const rol = evento.target.closest('[data-editar-permisos]');
    if (rol) { editarPermisos(rol); return; }

    if (evento.target.closest('[data-accion="limpiar-filtros"]')) {
      buscador.value = '';
      filtros.rol = '';
      filtros.estado = '';
      marcarChip('rol', '');
      marcarChip('estado', '');
      aplicarFiltros();
    }
  });

  cambiarPestana('usuarios');
})();
