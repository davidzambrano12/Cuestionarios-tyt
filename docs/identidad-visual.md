# Identidad visual en la interfaz

Cómo se aplica el **Manual de Identidad Visual UNIPUTUMAYO (versión 01-2025)** en el simulador.
Los valores viven en [`static/css/tokens.css`](../static/css/tokens.css); los componentes de
[`static/css/styles.css`](../static/css/styles.css) y los templates solo usan esos tokens.

## 1. Colores del manual

| Color | Uso según el manual | Pantalla (manual) | Token |
|---|---|---|---|
| Azul | Seguridad, confianza. Documentos oficiales y color dominante | RGB 25, 102, 143 · `#18668F` | `--azul-600` (= `--color-primario`) |
| Verde | Naturaleza, crecimiento. Acompaña al azul en lo institucional | RGB 128, 191, 31 · `#80BF1F` | `--verde-500` |
| Naranja | Creatividad, energía. Acompaña al azul en lo digital | `#F5A51D` | `--naranja-500` |
| Gris | Primario neutro | `#595957` | `--gris-600` |
| Negro | Secundario (máx. 30 % de uso) | `#000000` → texto `#231F20` | `--gris-900` |
| Gris claro | Secundario (máx. 30 % de uso) | `#B2B6B9` | `--gris-300` |

### Inconsistencias del manual y cómo se resolvieron

- **Verde:** el hexadecimal impreso `#bf1f50` es una errata (es un rojo). Se usa el RGB 128, 191, 31 → `#80BF1F`.
- **Azul:** el logotipo del PDF está dibujado en `#0080AB`, distinto del valor de pantalla declarado (`#18668F`).
  Se toma el valor declarado como color principal porque cumple AA con texto blanco (6.29:1); `#0080AB`
  queda como `--azul-500`, **solo** para acentos e iconos (con texto blanco da 4.49:1, no alcanza AA).
- **Naranja:** el RGB impreso (254, 166, 31) no coincide con su hexadecimal; se usa el hexadecimal `#F5A51D`.

## 2. Reglas de combinación y contraste (WCAG 2.1)

Verde, naranja y gris claro son colores claros: **nunca llevan texto blanco** (≈ 2:1).
Para usarlos como texto o como fondo de botón se emplea su tono oscuro de la escala.

| Combinación | Contraste | Nivel | Dónde |
|---|---|---|---|
| `--gris-900` sobre blanco | 16.30 | AAA | texto principal |
| `--gris-600` sobre blanco | 7.02 | AAA | texto secundario |
| `--gris-500` sobre blanco | 5.35 | AA | metadatos, ayudas |
| blanco sobre `--azul-600` | 6.29 | AA | botón primario |
| blanco sobre `--azul-700` | 8.06 | AAA | botón primario (hover) |
| `--azul-700` sobre `--azul-50` | 7.32 | AAA | badge informativo |
| `--verde-700` sobre blanco | 5.36 | AA | texto de éxito / aprobado |
| blanco sobre `--verde-700` | 5.36 | AA | botón de éxito |
| `--verde-800` sobre `--verde-50` | 7.30 | AAA | badge "Aprobado" |
| `--gris-900` sobre `--verde-500` | 7.29 | AAA | chip con verde de marca |
| `--naranja-700` sobre blanco | 5.04 | AA | texto de aviso |
| `--naranja-800` sobre `--naranja-50` | 6.83 | AA | badge de aviso / en curso |
| `--gris-900` sobre `--naranja-500` | 7.98 | AAA | chip con naranja de marca |
| `--rojo-700` sobre `--rojo-50` | 6.87 | AA | badge "Reprobado", errores |
| blanco sobre `--rojo-600` | 5.62 | AA | botón destructivo |
| `--gris-400` sobre blanco | 3.46 | UI 3:1 | borde de campos de formulario |

Prohibido: texto blanco sobre `--verde-500`, `--naranja-500`, `--azul-500` o `--gris-300`.

### Proporción de uso

- Azul: color dominante (navegación, botones primarios, enlaces, estados activos).
- Verde: éxito, aprobación, progreso; acentos institucionales.
- Naranja: avisos, elementos "en curso" y llamados de atención puntuales.
- Negro y gris claro: complementarios, nunca más del 30 % de la composición (manual p. 22).
- Rojo: no es color de marca; solo errores, reprobado y acciones destructivas.

## 3. Tipografía

| Rol | Fuente (manual) | Pesos | Token |
|---|---|---|---|
| Logotipo | Heavitas | — | no se usa como texto de interfaz |
| Títulos | Raleway (primaria) | 600, 700, 800 | `--fuente-titulos` |
| Interfaz, tablas, formularios | Roboto (apoyo) | 400, 500, 700, itálica | `--fuente-texto` |
| Textos de lectura larga (Lectura Crítica) | Fira Sans (apoyo) | 400, 600, itálica | `--fuente-lectura` |

- Raleway trae cifras antiguas por defecto: en títulos y métricas se fuerzan cifras alineadas (`lining-nums`).
- Notas, tiempos y tablas usan cifras de ancho fijo (`tabular-nums`) para que no "bailen".

### Escala de tamaños

| Token | Tamaño | Uso |
|---|---|---|
| `--texto-xs` | 12 px | badges, metadatos (mínimo para texto funcional) |
| `--texto-sm` | 13 px | texto secundario, celdas de tabla |
| `--texto-base` | 14 px | interfaz: botones, campos, navegación |
| `--texto-md` | 16 px | párrafos, enunciados de preguntas |
| `--texto-lg` | 18 px | títulos de tarjeta, subtítulos |
| `--texto-xl` | 20 px | títulos de sección |
| `--texto-2xl` | 24 px | títulos de página secundarios |
| `--texto-3xl` | 30 px | título de página |
| `--texto-4xl` | 36 px | cifras destacadas |
| `--texto-display` | 48 px | calificación final |

Interlineado: 1.2 (títulos grandes), 1.3 (títulos), 1.5 (interfaz), 1.7 (lectura).

## 4. Cómo usarlo

```css
/* Bien: semántico */
.alerta { background: var(--color-aviso-suave); color: var(--color-aviso-texto); }

/* Mal: color fijo o color de marca claro con texto blanco */
.alerta { background: #F5A51D; color: #fff; }
```

- En componentes, preferir tokens semánticos (`--color-texto`, `--color-exito-suave`…).
- Los primitivos (`--azul-600`, `--verde-700`…) están disponibles cuando se necesita un tono concreto de la escala.
- No escribir colores hexadecimales en templates ni en `styles.css`.
