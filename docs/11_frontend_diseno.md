# 11 · Sistema de diseño del frontend ("Centinela Glass")

Inspirado en una referencia de dashboard inmobiliario (solo guía de estilo). Todo el contenido sigue siendo dato real de la API.

## Tokens (`frontend/tailwind.config.js`, `frontend/src/index.css`)
- **Fondo:** degradado menta → cielo con luces lima/aqua (`body`), fijo al scroll.
- **Superficies:** `.glass` (vidrio esmerilado, borde blanco), `.glass-strong` (modales, chat, sidebar móvil), radios `rounded-3xl/4xl`, controles en píldora (`rounded-full`).
- **Paleta:** `slate` remapeado a tinta verde-azulada (`slate-900 = #10211f`), `emerald` más sereno; acentos pastel `lime`, `aqua`, `blush` (+ `-soft`, `-ink`).
- **Tipografía:** Outfit (sans) y JetBrains Mono (ids/hashes).
- **Utilidades:** `.icon-btn`, `.section-eyebrow`, `.no-scrollbar`, animaciones `animate-fade-up` / `animate-slide-in`.

## Layout
- `Sidebar`: panel de vidrio flotante en ≥ lg; cajón deslizante en móvil (botón menú en `Topbar`). Ítem activo = píldora oscura; tarjeta flotante del decisor activo abajo.
- `Topbar`: título grande + subtítulo por pantalla, controles del reloj simulado (fecha, hitos, +1d/+7d, reiniciar) en píldoras con scroll horizontal en móvil.
- `BandejaDecisiones`: resumen con mosaicos pastel (pendientes / ejecutadas / críticas) y barra de resolución, tarjetas de alerta de vidrio, y columna **Actividad reciente** (xl+) construida con las alertas reales ordenadas por corte.

## Desarrollo local
`frontend/.env.local` (ignorado por git) con `VITE_API_KEY`; `.claude/launch.json` define el servidor `frontend` (puerto 5173).
