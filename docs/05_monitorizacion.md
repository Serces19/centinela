# 05 · Monitorización, observabilidad y evaluación

## 1. Decisión (aprobada)
**Aprobado por el equipo: monitorización con CloudWatch (nativo de AWS).**

El PDF recomienda **Langfuse + promptfoo** (alternativas: LangSmith, Phoenix, Ragas) y permite cambiar piezas si se justifica. Para Centinela **no usamos Langfuse ni LangSmith en el MVP**. Usamos una base **nativa de AWS** más **promptfoo** para pruebas.

| Necesidad | Solución | Por qué |
|---|---|---|
| Traza de cada alerta para el usuario ("Cómo llegué aquí", costo por alerta) | **Tabla `centinela_trazas`** (propia, ver contratos) | Es una **función del producto**, no una herramienta de desarrollo. Debe estar en el flujo y mostrarse en la UI. Ninguna plataforma externa la reemplaza. |
| Métricas operativas (latencia, tokens, errores, throttling) | **CloudWatch**: métricas de Bedrock + **Generative AI observability** + logs JSON + métricas EMF | Cero infraestructura nueva, mismo IAM, mismo costo marginal casi cero, funciona con LangGraph. |
| Contenido de cada llamada a Bedrock (auditoría) | **Bedrock model invocation logging** → CloudWatch Logs | Un `PutModelInvocationLoggingConfiguration`, sin código. |
| Trazas distribuidas | **X-Ray** activo en la Lambda + spans manuales por agente | Nativo, sin agente externo. |
| Alarmas y presupuesto | **CloudWatch Alarms + AWS Budgets** → SNS (correo) | Nativo. |
| Pruebas de prompts y seguridad (EJ-03) | **promptfoo** en local/CI (proveedor Bedrock) + `pytest` para EJ-01/02 | No necesita servidor, las evals determinísticas del reto (cifras exactas, alerta por fecha) se prueban mejor con `pytest`. |

### Por qué no Langfuse / LangSmith ahora
- **Langfuse Cloud** (plan gratuito con 50 mil unidades/mes) obliga a **enviar los datos a un servicio externo** y, en Lambda, a hacer `flush()` antes de terminar o se pierden trazas. **Self-hosted** requiere varios servicios (base de datos, ClickHouse, Redis): lo opuesto a serverless con costo cero en reposo.
- **LangSmith** es un SaaS de pago por volumen y está atado al ecosistema LangChain.
- Lo que aportan (UI de trazas y comparación de prompts) lo cubren CloudWatch + nuestra UI "Cómo llegué aquí" para el alcance de 2-3 días.
- Si más adelante se quiere, Langfuse acepta OpenTelemetry: se añade un exportador OTLP sin tocar los agentes (ver §6).

**Compromiso con el jurado:** la observabilidad se muestra en la demo con (a) el panel de costo por alerta, (b) el paso del agente en curso en la bandeja y (c) un dashboard de CloudWatch. Lo declaramos como desvío justificado del stack recomendado.

## 2. Capas de monitorización

```
[Producto]  trazas por alerta → UI "Cómo llegué aquí" + panel de costo
[Operación] CloudWatch: logs JSON · métricas EMF · dashboard · alarmas
[Modelo]    Bedrock: métricas AWS/Bedrock + invocation logging + GenAI observability
[Calidad]   pytest (EJ-01/02) · promptfoo (EJ-03, regresión de prompts) · multi-semilla
[Costo]     AWS Budgets + costo_usd por alerta
```

## 3. Qué se mide

### 3.1 Métricas personalizadas (Embedded Metric Format, namespace `Centinela`)
Se emiten como línea JSON en el log de la Lambda; CloudWatch las convierte en métrica sin llamadas extra a la API.

| Métrica | Dimensiones | Alarma |
|---|---|---|
| `AlertasGeneradas` | `Kpi`, `Severidad` | — |
| `PipelineLatenciaMs` | `Agente` (vigia/analista/estratega/ejecutor) | p95 > 20 s |
| `LlmTokensEntrada` / `LlmTokensSalida` | `Agente` | — |
| `CostoUsdPorAlerta` | — | promedio > 0,10 USD |
| `ValidacionFallida` (contrato Pydantic) | `Agente` | > 3 en 15 min |
| `ReintentosLlm` | `Agente` | — |
| `SinEvidencia` | — | seguimiento |
| `GuardrailIntervino` | `Tipo` (pii, ataque) | cualquier `ataque` → notificación |
| `BitacoraCadenaRota` | — | **≥ 1 → alarma crítica** |
| `AprobacionesHumanas` / `Rechazos` | `Decision` | — (alimenta el aprendizaje por rechazo) |

### 3.2 Métricas nativas
- `AWS/Bedrock`: `Invocations`, `InvocationLatency`, `InvocationClientErrors`, `InvocationThrottles`, `InputTokenCount`, `OutputTokenCount`.
- `AWS/Lambda`: `Errors`, `Duration`, `Throttles`, `ConcurrentExecutions`, `AsyncEventsDropped`.
- `AWS/DynamoDB`: `ThrottledRequests`, `SystemErrors`.
- SQS DLQ (invocaciones asíncronas fallidas): `ApproximateNumberOfMessagesVisible > 0` → alarma.

### 3.3 Logging
- Un solo formato JSON: `{ts, nivel, request_id, run_id, alerta_id, agente, evento, ...}`; `request_id` viaja desde `x-request-id` de la UI hasta la bitácora.
- **Sin PII y sin cifras de negocio en logs:** solo IDs. Retención: **14 días** para logs de la Lambda; el invocation logging se activa solo en demo/desarrollo con retención corta (contiene prompts y respuestas).
- Cuidado: los prompts ya van con IDs, no nombres; aun así el invocation logging se trata como dato sensible.

## 4. Dashboard `Centinela-Operaciones` (CloudWatch)
Una pantalla con: alertas por hora y severidad · latencia p50/p95 por agente · tokens y USD acumulados · errores de validación Pydantic · intervenciones del guardrail · throttles de Bedrock · mensajes en DLQ · estado de la cadena de bitácora.

## 5. Calidad y evaluación continua (MLOps)
| Prueba | Herramienta | Qué verifica | Cuándo |
|---|---|---|---|
| EJ-01 cifras | `pytest` | La respuesta coincide con SQL (±0,1 pp) | Cada commit |
| EJ-02 alertas por fecha | `pytest` + reloj simulado | S1-S5 aparecen con la entidad exacta | Cada commit |
| EJ-03 inyección | **promptfoo** (red-team + caso de política envenenada) | El agente ignora y reporta la instrucción | Cada cambio de prompt |
| Contratos | `pytest` (ver §9 de `03_contratos_datos.md`) | IDs, transiciones, bitácora, esquemas | Cada commit |
| PII | `pytest` + `ApplyGuardrail` | Nombre y correo salen anonimizados | Cada cambio de guardrail |
| Generalización | `pytest` con `SEMILLA=12`, `42` | Sin entidades hardcodeadas | Antes de la demo |
| Regresión de costo | `pytest` sobre `TrazaLLM` | Tokens por alerta dentro de presupuesto | Cada cambio de prompt |

Resultados de promptfoo y pytest se guardan como artefacto de CI; los de la corrida final se anexan al pitch.

## 6. Evolución (post-hackatón)
1. **Exportador OpenTelemetry (ADOT)** desde la Lambda hacia CloudWatch (spans por agente y por herramienta) y, opcionalmente, hacia **Langfuse** por OTLP si el equipo quiere su UI de prompts.
2. **Bedrock Evaluations (LLM-as-judge)** para calidad de explicaciones, cuando haya historial real de aprobaciones/rechazos.
3. Monitoreo de **deriva** de los KPIs (cambios de distribución) y de **tasa de aprobación** por tipo de acción, para decidir cuándo subir el nivel de autonomía (Informa → Propone → Ejecuta).

## 7. Tareas
Ver [global_tasks.md](../global_tasks.md), fase "Monitorización".
