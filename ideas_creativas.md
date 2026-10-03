# Ideas creativas · Centinela (diferenciadores)

## Prioridad A: entran al MVP (bajo costo, alto efecto en el jurado)
> Excepción: el backtest (1) y el explorador de cola larga (6) son **opcionales**, al final de `global_tasks.md`, solo si sobra tiempo.
1. **(Opcional) Backtest con reloj simulado ("máquina del tiempo")** — correr el Vigía día a día sobre los 12 meses y reportar por escenario: *día de primera detección, días de anticipación vs. la regla de política, $ evitables*. Pitch: "Centinela habría avisado el S1 N días antes". Nadie más traerá una métrica de anticipación.
2. **Arnés de evaluación multi-semilla** — `SEMILLA=1..20` con el generador; precisión/recall por escenario, informe en CI. Prueba que no está memorizado y da el score "pruebas del jurado" por adelantado. (MLOps)
3. **Impacto en pesos calculado, no generado** — Estratega recibe de Python el $ recuperable (Δprecio × volumen 90d, exceso de descuento, cartera en riesgo, margen perdido) con intervalo (bootstrap) → "confianza" respaldada por datos.
4. **Una causa = una alerta (correlación)** — agrupar por entidad raíz (proveedor PR08, vendedor V03). S1 afecta 4 SKU y 1 línea: una alerta, no cinco.
5. **Panel "Costo de Centinela"** — tokens/USD por alerta vs. $ en riesgo detectado (ROI visible).

## Prioridad B: para ganar el escenario oculto
6. **(Opcional) Explorador de cola larga** — barrido automático de cortes (línea×bodega×segmento×vendedor×proveedor×canal×ciudad) con CUSUM/PELT y z-score robusto (MAD) sobre margen, ticket, devoluciones/cancelaciones, lead time real vs. pactado. Candidatos hoy: P0097 vendido bajo costo (42 líneas), Alimentos < mínimo, cancelaciones por canal.
7. **Detector de ventas bajo costo** — política COM-POL-002 lo prohíbe sin Gerencia General; chequeo gratuito y trazable. Hay 116 líneas no canceladas con precio neto < costo ($2.721.412), pero 37 son consecuencia de S1 y 42 de un SKU (P0097): hipótesis del escenario oculto, sin confirmar.

## Prioridad C: hoja de ruta / pitch comercial
8. **Aprendizaje por rechazo** — motivo de rechazo → tabla `feedback` → few-shot al Estratega y supresión/umbral por tipo+responsable.
9. **Niveles de autonomía por acción** (Informa/Propone/Ejecuta) con "historial de aciertos" calculado de la bitácora → ruta a producción.
10. **Visión por computador:** ingesta de documentos (OC/factura escaneada o foto de góndola) con Textract/Bedrock vision, y **detector de texto oculto** (blanco sobre blanco, metadatos) antes de pasar documentos al LLM — defensa de inyección multimodal.
11. **Alertas por WhatsApp/Slack** con botón aprobar/rechazar (EventBridge→SNS).
12. **Playbooks por rol** (Gerente 30 s vs. Analista detalle) y modo "explícame como CFO".
