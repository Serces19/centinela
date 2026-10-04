# 03 · Contratos y datos (Pydantic v2)

Todos los mensajes entre componentes son modelos Pydantic v2 con `extra="forbid"` en `backend/contracts/`. **El código es la fuente de verdad**; este documento explica las reglas y dónde está cada cosa. El mismo modelo valida la API, define el esquema de *tool use* de Bedrock, se persiste en DynamoDB y alimenta las evals (`evals/test_contratos.py`).

## 1. Reglas de diseño
1. **El LLM nunca escribe dinero.** El modelo produce un borrador (`DiagnosticoLLM`, `SeleccionEstratega`) y el servidor calcula el impacto (`ImpactoCalculado`, `tools/impacto.py`) con consultas registradas.
2. **Las cifras se citan, no se escriben.** El texto del modelo lleva marcadores `{c1}`, `{c2}`… que apuntan a la lista `cifras: list[CifraTrazable]` (valor, unidad, `consulta_id`). `numeros_sueltos()` rechaza cualquier dígito y cualquier número escrito con letras ("cuatro", "veinte") fuera de IDs y fechas; la excepción es `numeros_politica`: números que aparecen literalmente en el fragmento de política citado (p. ej. "25 %" de OPE-POL-007). Ante un rechazo se reintenta con el error como `toolResult`; si persiste, plantilla determinista.
3. **Privacidad por construcción:** los contratos que ve el modelo usan IDs (`V03`, `C0496`, `PR08`), no nombres. La UI resuelve nombres en `services/resolucion.py`.
4. **Consultas registradas:** toda consulta que alimenta una cifra queda como `ConsultaRegistrada` (`consulta_id = Q-<sha256(sql|corte)[:12]>`, SQL con el corte como literal, hasta 300 filas, hash del resultado), guardada en `centinela_trazas` (PK `QUERY#<id>`) y servida en `GET /consultas/{id}`. Misma consulta y corte → mismo id.
5. **Estados cerrados:** `EstadoAlerta` y `transicion_valida()` (`base.py`); `rechazada → nueva` solo vía `reabrir`.

## 2. Mapa de contratos

| Archivo | Contratos principales |
|---|---|
| `base.py` | `Contrato`, IDs validados por regex, `Kpi`, `Vista`, `Severidad`, `EstadoAlerta`, `TipoEntidad`, `EntidadRef`, `transicion_valida` |
| `evidencia.py` | `ConsultaRegistrada`, `CifraTrazable` (unidades: COP, %, pp, dias, unidades, veces, lineas, semanas, pedidos, skus, clientes), `CitaPolitica`, `numeros_sueltos`, `referencias_cifras`, `formatear_cifra`, `renderizar_texto` |
| `alertas.py` | `Hallazgo`, `Alerta` (`huella_causa`, `dinero_en_riesgo_cop`, `paso_actual`), `AlertaVista`, `ResumenAlertas` (total en riesgo, conteos por severidad, `decisiones_clave`) |
| `agentes.py` | `DiagnosticoLLM`/`DiagnosticoBorrador`, `CitaElegida`; acciones tipadas (`AjustePrecio`, `ContactoCartera`, `ExpeditarOC`, `RevisionDescuentos`, `ReactivarCliente`, `RenegociarProveedor`, `CorregirVentaBajoCosto`); `SeleccionAccion`/`SeleccionEstratega`; `ImpactoCalculado`, `Accion`, `Propuesta` (`cifras`, `aprendizaje`) |
| `decision.py` | `DecisionRequest` (aprobar/editar/rechazar; motivo ≥ 10 caracteres al rechazar), `Borrador`, `ResultadoEjecucion` |
| `bitacora.py` | `Evento`, `EntradaBitacora` (hash SHA-256 encadenado), `verificar_cadena` |
| `configuracion.py` | `ConfigUmbral`, `ConfiguracionVigia` (umbrales y autonomía por familia), `ConfiguracionUpdate` |
| `herramientas.py` | `ConsultarVistaIn/Out`, `BuscarPoliticaIn/Out`, `FragmentoPolitica`, `PipelineEvent` |
| `operacion.py` | `TrazaLLM`, `CostoAgente`, `ResumenCostos`, chat (`ChatRequest`, `RefCifra`, `RefGrafico`, `RespuestaChat`, eventos `ChatPaso/Token/Cifra/Grafico/Fin/Error`), `SimulacionResp` (`alertas_detectadas`, `alertas_nuevas`), `ErrorAPI` |

## 3. API (todas con `x-api-key`, salvo `/health`)

| Método y ruta | Qué hace |
|---|---|
| `GET /health` | Salud (público). |
| `GET /simulacion/corte` · `POST /simulacion/avanzar` · `POST /simulacion/reiniciar` | Reloj simulado; avanzar ejecuta el Vigía y persiste alertas. Reiniciar borra alertas/trazas/feedback pero **no la bitácora**. |
| `GET /alertas` · `GET /alertas/{id}` | Lista y detalle (`AlertaVista`: alerta + propuesta + nombres resueltos). |
| `GET /alertas/resumen` | Dinero total en riesgo sin doble conteo, severidades y 3 decisiones clave (primera por familia, orden severidad y dinero). |
| `POST /alertas/{id}/procesar` | Analista → Estratega. |
| `POST /alertas/{id}/decision` | Aprobar / editar / rechazar. Cabeceras `Idempotency-Key` e `If-Match` (versión). |
| `POST /alertas/{id}/reabrir` | `rechazada → nueva`; el nuevo análisis usa el rechazo como aprendizaje. |
| `GET /consultas/{id}` | SQL, filas y hash de una consulta registrada. |
| `GET /bitacora` · `GET /bitacora?alerta_id=` | Auditoría general (filtros actor/evento) o cadena de una alerta con `cadena_valida`. |
| `GET /costos` | Costo real por agente y por alerta desde `trazas`. |
| `GET /config` · `PUT /config` | Umbrales del Vigía y autonomía por familia (la autonomía `ejecuta` está bloqueada). |
| `POST /chat` | SSE (`paso`, `token`, `cifra`, `grafico`, `fin`, `error`). |

Errores: `ErrorAPI` con código (`no_autorizado`, `conflicto_version`, `transicion_invalida`, …).

## 4. DynamoDB

| Tabla | PK | SK | Contenido |
|---|---|---|---|
| `centinela_alertas` | `alerta_id` | `META` | `Alerta` + `Propuesta`; `version` para bloqueo optimista; GSIs `gsi_estado` (`estado`, `dinero_en_riesgo_cop`) y `gsi_huella` |
| `centinela_bitacora` | `alerta_id` | `seq` | `EntradaBitacora` append-only; el rol de la Lambda tiene `Deny` de `UpdateItem`/`DeleteItem` |
| `centinela_trazas` | `alerta_id` (o `QUERY#<id>`, `CHAT#<run_id>`) | `ts_tipo` | `TrazaLLM` y `ConsultaRegistrada`; TTL 30 días |
| `centinela_reloj` | `RELOJ` | `ACTUAL` | `{corte, run_id}` |
| `centinela_config` | `clave` | — | Umbrales y autonomía (`CONFIG#…`) y feedback de rechazos (`FEEDBACK#…`) |

## 5. Verificación
`uv run pytest evals/` (cada contrato, transiciones, cadena de bitácora, rechazo de números sueltos, referencias de cifras del chat, truncado de resultados). Las pruebas con Bedrock usan el modelo real; las de persistencia usan el backend `memory` (ver `evals/conftest.py`).
