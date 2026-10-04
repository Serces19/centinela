# 10 · Auditoría del sistema (2026-10-04)

**Criterios:** (1) cumplir los requisitos del PDF del reto (láminas 6-19), (2) "menos es más": claridad del MVP, (3) lo que se afirma en los documentos coincide con lo que el sistema hace.
**Método:** lectura del código (`backend/`, `frontend/`, `infra/`), llamadas de solo lectura a la API desplegada y a Bedrock, consultas a los CSV oficiales y ejecución de `pytest` (75 pruebas pasan; 1 falla: `test_knowledge_base`; la suite se detuvo en ese fallo y se excluyó `test_multi_semilla`).
**Resultado corto:** la base técnica es sólida (contratos, bitácora encadenada, guardrails, 5 de 5 escenarios detectados, infraestructura desplegada). Pero hay **8 hallazgos críticos** que un jurado vería en la primera demo, y varias cifras de los documentos no se sostienen.

---

## 1. Cumplimiento de requisitos del PDF

Leyenda: ✅ cumple · ⚠️ cumple a medias · ❌ no cumple.

### 1.1 Alcance obligatorio del MVP (lámina 9)
| Requisito | Estado | Evidencia |
|---|---|---|
| Vigía detecta ≥ 3 de 5 escenarios | ✅ | Evals EJ-02: 5 de 5 al 2026-09-30. Pero ver C3 (ruido) y C4 (duplicados). |
| Analista explica la causa con evidencia | ⚠️ | Solo 14 de 388 alertas tienen propuesta; el texto de S1 tiene errores de contenido (ver C7). |
| Bandeja con aprobar / rechazar | ✅ | `DecisionModal.tsx` (aprobar, editar, rechazar con motivo). |
| Chat para preguntar sobre los datos | ❌ | La pregunta emblema del PDF falla en producción (ver C1). |
| Bitácora de cada decisión | ✅ | Cadena SHA-256 verificable por alerta. Falta vista global (ver §1.4). |

### 1.2 Recorrido del usuario (lámina 7)
| Paso | Estado | Evidencia |
|---|---|---|
| 1 Abre la bandeja, decisiones ordenadas por pesos en riesgo | ⚠️ | La API devuelve 388 alertas al corte 2026-08-15; S1 queda en la posición 34. La UI lo oculta filtrando por entidades fijas (C3). |
| 2 Abre una alerta: qué pasó, por qué, qué se propone, cuánto vale | ✅ | `DetalleAlertaModal.tsx`, 3 niveles, confianza y supuestos. |
| 3 Pregunta en lenguaje natural ("¿qué otros clientes compran esos SKU?") | ❌ | Respuesta en vivo: "No tengo evidencia suficiente" (C1). |
| 4 Decide; si rechaza, explica por qué **y Centinela aprende** | ⚠️ | El motivo se guarda (`guardar_feedback`) pero **nadie lo lee**: `obtener_feedback` no tiene llamadores. No aprende (C6). |
| 5 Queda registrado: el Ejecutor actúa y todo va a la bitácora | ✅ | Borradores `sandbox://` y bitácora encadenada. |

### 1.3 Backend (lámina 15) y API (lámina 16)
| Requisito | Estado | Evidencia |
|---|---|---|
| Capa semántica (7 vistas, sin tablas crudas) | ✅ | `semantic/views.sql`, validador en `tools/consultas.py`. |
| Reloj simulado que "mueve el reloj y **dispara al Vigía**" | ⚠️ | `avanzar_simulacion` solo actualiza el reloj y responde `pipeline_disparado=True`, que es falso. El Vigía corre de forma perezosa dentro de `GET /alertas`. |
| Ciclo de vida con estado persistido | ✅ | `EstadoAlerta` + DynamoDB. |
| Aprobación humana antes de toda acción | ✅ | `interrupt()` + estado `propuesta`. |
| Acciones seguras (lista cerrada, borrador) | ⚠️ | Lista cerrada y sandbox sí. Pero `estratega.py` tiene **IDs de respaldo inventados** (`C0496`, `P0119`, `V03`, `C0061`, `P0005…P0008`) si faltan entidades. |
| Priorización; "una misma causa no genera 10 alertas" | ❌ | 101 de 232 huellas de causa están duplicadas en la respuesta de la API (p. ej. `saldo_vencido|C0480` tres veces con distinto corte). |
| Costo y latencia (caché, tope, costo por alerta) | ⚠️ | Pipeline registra tokens reales. El chat reporta **costos inventados** (`150 * precio_in + 50 * precio_out`, constantes). |
| Robustez: reintentos, timeouts, "no tengo evidencia" | ✅ | Un reintento de validación; respuesta "sin evidencia" existe. |
| Endpoints: `/simulacion/avanzar`, `/alertas`, `/alertas/{id}`, `/decision`, `/chat`, `/bitacora` | ✅ | `api/main.py`. `/bitacora` exige `alerta_id` (no hay listado general). |

### 1.4 Frontend (láminas 17-18)
| Requisito | Estado | Evidencia |
|---|---|---|
| Bandeja | ✅ | `BandejaDecisiones.tsx`. |
| Detalle | ✅ | `DetalleAlertaModal.tsx`. |
| Chat anclado: "respuestas con cifra, **gráfico** y fuente" | ⚠️ | Hay cifra y fuente; no hay ningún gráfico (Recharts solo en el panel de costo). |
| Bitácora: "quién aprobó qué, cuándo" | ⚠️ | Solo por alerta; no hay vista de auditoría general. |
| **Configuración**: KPIs vigilados, umbrales, responsables, autonomía | ❌ | `ConfiguracionPanel.tsx` es estado local de React (`useState`): no guarda, no hay endpoint y **el Vigía no lo lee**. Los valores por defecto (margen 15 %, descuento 8 %, cobertura 7) **no coinciden con la política**. |
| Valor en 30 segundos (dinero en riesgo + 3 decisiones clave) | ⚠️ | Depende del filtro con entidades fijas (C3). |
| Confianza y supuestos visibles | ✅ | |
| Agentes a la vista (paso en curso) | ⚠️ | Solo se muestra el estado (`en_analisis`), no el paso de cada agente. |
| Severidad no solo por color, teclado, celular | ➖ | No auditado. |

### 1.5 IA responsable (lámina 19)
| Riesgo | Estado | Evidencia |
|---|---|---|
| Cifras inventadas | ⚠️ | El validador `numeros_sueltos` se **evade escribiendo los números con letras** ("veinticinco por ciento"); el Analista de S1 afirma que los márgenes de los cuatro SKU "alcanzan el veinticinco por ciento"; con el costo nuevo y el precio de lista vigente quedan entre 5,8 % y 22,4 % (C7). En el chat, `consulta_id="Q-ALERTA-DIRECTA"` no cumple el patrón del contrato. |
| Acción no deseada | ✅ | Aprobación + sandbox. |
| Inyección de instrucciones | ✅ | EJ-03 pasa con el guardrail. |
| **Acceso indebido a datos** | ❌ | **La API no tiene autenticación** (C2). "Roles por área" es solo un selector de persona en la UI; `decidido_por` lo envía el cliente. |
| Datos personales (Ley 1581) | ✅ | IDs hacia el modelo + Guardrails anonimiza. |
| Trazabilidad | ✅ | Bitácora encadenada. |
| Degradación del agente (evals en cada cambio) | ⚠️ | Hay CI y evals, pero `test_knowledge_base` falla hoy (C5) y EJ-02.1 se declaró "aprobado" con 129 alertas en el corte "limpio". |
| Niveles de autonomía por tipo de acción | ❌ | Solo en la pantalla decorativa de Configuración. |

---

## 2. Hallazgos críticos (ordenados por daño en la demo)

**C1 · El chat falla en la pregunta emblema del PDF.** Probado en producción con tres variantes ("¿qué otros clientes compran los SKU P0001 y P0006?", "¿qué otros SKU le compramos al proveedor PR08?" y la misma anclada a la alerta de S1): las tres responden "No tengo evidencia suficiente". Causas: (a) `chat.py` es un conjunto de plantillas por palabra clave, no un agente con herramientas; (b) la plantilla de proveedor filtra `v_cobertura_inventario` por una columna `proveedor_id` que **no existe** en la vista; (c) la ruta con Bedrock está detrás de `CENTINELA_BEDROCK_CHAT`, que en la Lambda **no está definida**, así que nunca se ejecuta; (d) `Q-ALERTA-DIRECTA` rompe el contrato `ConsultaId` en la ruta "alerta directa".

**C2 · API pública sin autenticación.** La Function URL es abierta y el backend **nunca valida `x-api-key`** (solo el cliente la envía). Cualquiera puede reiniciar el reloj, lanzar análisis con Bedrock (costo), registrar decisiones o llamar al chat. Probado: `GET /alertas` responde 200 sin credenciales.

**C3 · La interfaz oculta el ruido con entidades fijas.** `frontend/src/utils/alertas.ts` clasifica "alertas estratégicas" comparando contra `PR08`, `C0496`, `P0119`, `V03`, `C0061` y escribe títulos como "+25 %" y "$23.5M"; `esCorteInicialLimpio` oculta todo en el corte limpio (la API devuelve 129 alertas ahí). Con otra semilla, con el dataset del jurado o con el escenario oculto, esas alertas **desaparecerían de la bandeja**. Contradice la regla de generalización y la de datos reales. Las 388 alertas vienen de reglas con umbrales muy bajos: con las reglas oficiales hay 55 clientes con más de 15 días vencidos ($120 M) y 33 clientes con más de 3 veces su intervalo de compra al 2026-09-30, cuando el escenario real es uno solo.

**C4 · Sin deduplicación entre cortes y dinero en riesgo inflado.** Cada corte crea alertas nuevas para la misma causa (`ALR-<corte>-…`). La suma de `dinero_en_riesgo_cop` de la respuesta es ≈ $2.924 M COP, cuando toda la cartera abierta del dataset es $3.512 M. No es un número presentable como "dinero en riesgo".

**C5 · La Knowledge Base devuelve documentos ajenos y duplicados.** El índice de S3 Vectors (`bedrock-knowledge-base-default-index`) lo comparte la KB de Centinela con otra KB de la cuenta (`legal-ai-scope-knowledge-base`). Una consulta real devuelve un fragmento de `compendio-2024-2025-15-136.pdf` (texto sobre "La Presidenta o el Presidente del Estado…") etiquetado como `FIN-POL-004`. Además cada política está subida dos veces (nombre canónico y nombre original), así que cada fragmento sale duplicado. El Analista puede citar texto que no es de la política.

**C6 · "Centinela aprende" no aprende.** El motivo de rechazo se escribe en `centinela_config`; ningún agente lo consulta. Es un requisito explícito del recorrido del usuario.

**C7 · Calidad del diagnóstico de S1.** Con los datos reales (lista de precios vigente y costo desde el 2026-08-15), el margen de los SKU queda en: P0001 12,9 %, P0006 5,8 %, P0011 10,8 % y P0021 22,4 %. El Analista dice que "alcanzan el veinticinco por ciento" y solo habla de un alza "de más del cinco por ciento" (fue 25 %; la regla de números sueltos le impide citar la cifra en el texto). La acción propuesta es subir el precio 5,5 %: para P0001 reponer el 25 % exigiría cerca de +16 %. Y el impacto de $23,5 M es el sobrecosto mensual, no lo "recuperable" con esa acción. El jurado leerá este texto en el minuto 2 de la demo.

**C8 · Cifras de los documentos de demo y pitch que no se sostienen.**
- Backtest: S2 y S5 aparecen "detectados el 2025-10-14 y el 2025-10-13 (+351 y +352 días)", cuando esos escenarios empiezan meses después (S2 en abril, S5 en julio). Son alertas por pagos normales, no los escenarios. Con esos datos el promedio de anticipación no es "+18 a +25 días"; el titular es inconsistente con su propia tabla.
- "Dinero protegido": la tabla suma $45,0 M, no los "$115 M" ni el "ROI > 10.000×" del pitch.
- Costos "$0,02 a $0,04 por alerta" y "$0,04 por ciclo": no hay medición que los respalde (el chat usa constantes).
- Guion de demo: menciona `P0016` (no es SKU de S1; son P0021, P0001, P0011 y P0006), "Proveedor Alimentos del Valle" (PR08 es "Hogar Total Importaciones"), y "bandeja con 0 alertas de crisis" en el corte limpio (el backend tiene 129; solo la UI las oculta).
- EJ-02.1 ("corte limpio") quedó marcado ✅ con 129 alertas: el criterio se aflojó en lugar de arreglar el ruido.
- Impacto de S1: el sistema calcula $23.522.184; los documentos dicen $23.558.346 (diferencia de ventana de 30 días). Hay que unificar.

---

## 3. Qué recortar o simplificar ("menos es más")

| Elemento | Problema | Decisión recomendada |
|---|---|---|
| `chat.py` con plantillas por palabra clave | Frágil, no cubre preguntas libres | **Un solo camino:** Haiku con `tool use` sobre `consultar_vista` (y `buscar_politica`); borrar los casos A-E. |
| `knowledge.py` (417 líneas, 3 modos: KB, Titan híbrido, local con caché de embeddings) | 3 rutas para 3 PDFs de 1.500 tokens | **Un solo camino** (KB con índice propio, o políticas en el prompt). Borrar el híbrido local. |
| `_crear_accion_fallback` y diagnóstico de respaldo | Fabrican acciones con IDs fijos cuando falla el modelo | Si el modelo falla: estado `sin_evidencia`. Cero respaldo inventado. |
| Filtro "estratégica" del frontend | Entidades fijas | Borrar; priorizar por reglas (dinero, severidad) en el backend. |
| Pantalla de Configuración | Decorativa | Reducirla a lo que realmente funciona (ver P0-5) o sacarla del MVP y declararla hoja de ruta. |
| Persona switcher + `decidido_por` del cliente | Parece autenticación y no lo es | Mantener solo como "rol de demo" etiquetado, con la clave de API como control real. |
| Documentación: 11 archivos (~1.800 líneas) | Duplicación y cifras en conflicto | Consolidar en 4: `README`, `negocio`, `arquitectura` (incluye contratos y monitorización resumidos) y `demo-pitch`; mover los informes generados a `docs/informes/`. |
| `scripts/` (11 scripts, uno de 519 líneas) y `temp_seed_*` en la raíz | Ruido en el repositorio | Dejar `deploy_all`, `build_duckdb`, `ejecutar_evaluacion_jurado`; mover o borrar el resto; mover `temp_seed_*` a `.gitignore`/`/tmp`. |
| Backtest y cola larga (opcionales) | Hoy presentan números engañosos | No usarlos en el pitch hasta corregir (ver P1-3). |

---

## 4. Plan de remediación priorizado

Esfuerzo: S ≤ 2 h · M ≤ 4 h · L > 4 h.

### P0 · Antes de cualquier demo
| # | Acción | Esfuerzo | Hecho cuando |
|---|---|---|---|
| P0-1 | **Chat real.** Reescribir `generar_respuesta_chat_stream` con Haiku + herramientas (`consultar_vista`, `buscar_politica`), contexto de alerta opcional, costo real de `usage`, `consulta_id` válidos. Añadir a `consultar_vista` lo necesario para "¿qué clientes compran esos SKU?" (agrupación sobre `v_ventas`). | L | Las 3 preguntas de la auditoría responden con cifra y fuente reales; EJ de chat en `evals/`. |
| P0-2 | **Autenticación mínima.** Middleware que exige `x-api-key` (valor en SSM, comparación en tiempo constante) en todo salvo `/health`; reserved concurrency y alarma de presupuesto ya existente. | S | `curl` sin clave → 401; la UI sigue funcionando. |
| P0-3 | **Bandeja explicable sin entidades fijas.** Borrar `clasificarEscenario`/`esAlertaEstrategica`; el backend devuelve `/alertas` ya deduplicado y ordenado, y la UI muestra "las 3 decisiones clave" por $ y severidad, con el resto plegado. Quitar títulos con cifras fijas. | M | Con `SEMILLA=12` la bandeja muestra los escenarios de esa semilla sin tocar código del frontend. |
| P0-4 | **Deduplicar por huella entre cortes** (una alerta abierta por `huella_causa`; actualizar su corte/valor, no crear otra) y **calcular el total de dinero en riesgo sin doble conteo.** Subir umbrales operativos solo donde la política lo permite (agrupar por cliente: un cliente = una alerta). | M | 0 huellas duplicadas; el total no supera la cartera abierta. |
| P0-5 | **Configuración mínima real.** Tabla `centinela_config` con umbrales (de `metricas.yaml`/política como valores por defecto) y autonomía por tipo de acción; endpoints `GET/PUT /config`; el Vigía lee al menos margen, días de mora, cobertura, descuento e intervalo. Quitar los valores inventados. | M | Cambiar un umbral cambia las alertas del siguiente corte. |
| P0-6 | **KB limpia.** Crear un vector bucket/índice propio de Centinela, subir una sola copia de cada PDF (nombres canónicos), re-sincronizar y arreglar `test_knowledge_base`. | S | `Retrieve` devuelve solo fragmentos de las 3 políticas, sin duplicados. |
| P0-7 | **"Aprende":** inyectar en el prompt del Estratega los últimos rechazos con motivo del mismo tipo de acción/entidad (máx. 3) y mostrarlo en la propuesta ("Se ajustó por el rechazo anterior: …"). | M | Un rechazo con motivo cambia la propuesta siguiente, con test. |
| P0-8 | **Reloj que dispara de verdad:** `avanzar` persiste las alertas del Vigía (deduplicadas) y encola el análisis de las N principales; o dejar de afirmar `pipeline_disparado`. | S | La respuesta refleja lo que ocurrió; la bandeja se actualiza sin pasos extra. |

### P1 · Calidad del diagnóstico y credibilidad
| # | Acción | Esfuerzo |
|---|---|---|
| P1-1 | **Análisis sin números en el texto:** el modelo devuelve causa cualitativa y referencias a `cifras`; la UI arma las frases con los valores reales. Añadir al validador la detección de números escritos con letras. | M |
| P1-2 | **Acción coherente con la causa:** el porcentaje de ajuste lo propone Python (el que repone el margen mínimo de la línea, redondeado), no el modelo; el impacto se etiqueta "sobrecosto mensual" y "recuperable" por separado. | M |
| P1-3 | **Corregir informes y pitch:** reemplazar backtest por fechas de primera detección del **escenario** (no de cualquier alerta de la entidad), unificar impacto de S1, calcular el ROI con medición real, corregir `P0016`, nombres y "0 alertas". Marcar EJ-02.1 con un criterio honesto. | M |
| P1-4 | **Vista de bitácora general** (`GET /bitacora` sin `alerta_id`, paginado) con filtro por actor y evento. | S |
| P1-5 | **Un gráfico en el chat** cuando la respuesta trae una serie (p. ej. margen semanal), o quitar la promesa. | S |
| P1-6 | **Paso de agente visible:** guardar `paso_actual` (vigía/analista/estratega) en la alerta y mostrarlo. | S |

### P2 · Limpieza (menos es más)
Aplicar la tabla de la sección 3: un solo camino de recuperación de políticas, sin respaldos inventados, 4 documentos, scripts reducidos, `temp_seed_*` fuera del repositorio.

---

## 5. Lo que está bien y no se toca
Contratos Pydantic con pruebas, bitácora encadenada con detección de manipulación, guardrails (EJ-03 y PII), reloj simulado y vistas parametrizadas por corte, validador de consultas SQL, generalización por semilla en el backend, infraestructura con Terraform, monitorización con CloudWatch y evaluación continua.

## 6. Preguntas abiertas
1. ¿Las láminas 05-07 (criterios de evaluación) ya llegaron? Las prioridades P0 asumen que "demo funcional + chat + cifras correctas" pesa más que el resto.
2. ¿Se mantiene la decisión de Bedrock Knowledge Base? La auditoría recomienda arreglarla (P0-6); el plan B (políticas completas en el prompt) quita una pieza entera si el tiempo aprieta.
