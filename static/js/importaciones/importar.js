/**
 * Carga del archivo: muestra el nombre elegido, admite arrastrar y soltar y
 * valida extensión y tamaño antes de enviar (el servidor vuelve a validar).
 */
(function () {
  'use strict';

  const LIMITE_MB = 5;
  const form = document.getElementById('form-importar');
  const input = form.querySelector('input[type="file"]');
  const zona = form.querySelector('[data-ref="zona"]');
  const nombre = form.querySelector('[data-ref="nombre-archivo"]');

  function problema(archivo) {
    if (!archivo) return 'Selecciona el archivo Excel de la plantilla.';
    if (!/\.(xlsx|xlsm)$/i.test(archivo.name)) return 'El archivo debe ser .xlsx (Excel).';
    if (archivo.size > LIMITE_MB * 1024 * 1024) return `El archivo supera el límite de ${LIMITE_MB} MB.`;
    return '';
  }

  function mostrar() {
    const archivo = input.files[0];
    const error = problema(archivo);
    zona.classList.toggle('zona-archivo--error', Boolean(archivo && error));
    zona.classList.toggle('zona-archivo--lista', Boolean(archivo && !error));
    nombre.textContent = archivo
      ? `${archivo.name} (${(archivo.size / 1024).toLocaleString('es-CO', { maximumFractionDigits: 1 })} KB)${error ? ` · ${error}` : ''}`
      : 'Ningún archivo seleccionado';
  }

  input.addEventListener('change', mostrar);

  ['dragenter', 'dragover'].forEach((tipo) => zona.addEventListener(tipo, (evento) => {
    evento.preventDefault();
    zona.classList.add('zona-archivo--arrastrando');
  }));
  ['dragleave', 'drop'].forEach((tipo) => zona.addEventListener(tipo, () => zona.classList.remove('zona-archivo--arrastrando')));
  zona.addEventListener('drop', (evento) => {
    evento.preventDefault();
    if (evento.dataTransfer.files.length) {
      input.files = evento.dataTransfer.files;
      mostrar();
    }
  });

  form.addEventListener('submit', (evento) => {
    const error = problema(input.files[0]);
    if (error) {
      evento.preventDefault();
      window.mostrarNotificacion(error, 'error', 'Revisa el archivo');
      zona.classList.add('zona-archivo--error');
    }
  });
})();
