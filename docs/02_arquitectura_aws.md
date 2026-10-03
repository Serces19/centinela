# 02 · Arquitectura AWS serverless (costo en reposo ≈ 0)

## Principio rector
Los números los calcula SQL/Python (DuckDB); el modelo razona, explica y redacta. Todo número en una respuesta enlaza la consulta que lo produjo.

## Decisión clave: DuckDB sobre Parquet en vez de Postgres/RDS
El dataset pesa ~12 MB en Parquet. Aurora Serverless / RDS cuestan en reposo y añaden VPC; Athena añade segundos de latencia y no tiene sentido para 270k filas.
**Lambda (contenedor) + DuckDB leyendo Parquet de S3** = consultas en ms, $0 en reposo, y el **reloj simulado** es un parámetro (`SET VARIABLE corte = '2026-03-15'`) que reemplaza `fecha_corte()`. Las 7 vistas de `03_capa_semantica.sql` se portan casi 1:1 (cambian `date_trunc`/casts menores). Se reusa la misma capa semántica para chat, Vigía y evaluación.

## Diagrama lógico
```
CloudFront + S3 (React+Vite)
        │ HTTPS
API Gateway HTTP ──► Lambda "api" (FastAPI+Mangum / Function URL streaming para chat SSE)
        │                    │
        │                    ├─► Step Functions (Standard)  ← Orquestador por alerta
        │                    │      1 Vigía (Lambda)  → detecta, dedup por causa raíz
        │                    │      2 Analista (Lambda, Bedrock Claude grande) → causa + evidencia + RAG
        │                    │      3 Estratega (Lambda) → 1-3 acciones, $ impacto, confianza
        │                    │      4 ⏸ waitForTaskToken  ← aprobación humana (aprobar/editar/rechazar)
        │                    │      5 Ejecutor (Lambda) → borrador de correo / tarea / OC en DynamoDB+SES draft
        │                    ▼
        │             DynamoDB: alertas · bitácora (hash encadenado) · feedback · costos por alerta
        ▼
S3: parquet/ (datos) · politicas/ (PDF→texto+chunks) · trazas/ (JSONL de cada consulta SQL)
Bedrock: Claude (razonar) + Haiku (clasificar) + Guardrails (PII, prompt-attack) + Titan Embeddings
EventBridge Scheduler: avance del reloj en modo demo / ejecución diaria del Vigía
CloudWatch + X-Ray: trazas; Bedrock invocation logging → S3
```

## Elecciones y por qué
| Capa | Elección | Motivo / alternativa descartada |
|---|---|---|
| Orquestación | **Step Functions + task token** | La pausa humana es nativa y auditable; sin servidor. (LangGraph vale si falta tiempo; se puede correr dentro de una Lambda con checkpoint en DynamoDB.) |
| LLM | **Bedrock** (Claude grande + Haiku) | Misma factura AWS, IAM, Guardrails. Tool use con **herramientas cerradas**: `run_sql(vista, filtros)`, `buscar_politica`, `crear_borrador`. |
| RAG | 3 PDFs ≈ 1,5 k tokens: **van completos en el prompt con prompt caching** y citan sección | Bedrock KB + OpenSearch Serverless cuesta cientos USD/mes mínimos; pgvector innecesario. Si crece: embeddings en Parquet + DuckDB. |
| Estado | **DynamoDB on-demand** | Alertas con ciclo de vida (Nueva→análisis→propuesta→aprobada/rechazada→ejecutada), bitácora append-only con `hash_prev` (inmutabilidad verificable) y Streams a S3. |
| Seguridad | Rol IAM solo-lectura al bucket de Parquet; el SQL pasa por validador (solo `SELECT` sobre vistas `v_*`); Guardrails + etiquetas `<documento>` para tratar políticas como datos, nunca órdenes | Cubre inyección (EJ-03 del jurado), acceso indebido y Ley 1581 (enmascarar nombres/IDs antes del LLM). |
| Frontend | **React + Vite + Tailwind + shadcn + Recharts** en S3/CloudFront | El PDF recomienda Next.js pero admite alternativas justificadas: no necesitamos SSR; Vite = deploy estático gratis. |
| IaC | **Terraform** (módulos: data, api, agents, front) | Preferencia + reproducibilidad: `terraform apply` en una cuenta limpia del jurado. |
| Observabilidad | CloudWatch + tabla `trazas` propia (alerta→consultas→tokens→USD) | Langfuse es externo; para 3 días lo propio basta y alimenta el "costo registrado por alerta". |
| Evals | pytest + generador con N semillas, en GitHub Actions | Ver diferenciadores. |

## Costo estimado de la demo
Lambda/S3/DynamoDB/API GW/Step Functions dentro de free tier o centavos. Único costo real: **tokens Bedrock** (topes por alerta, Haiku para clasificar, caché de políticas). Objetivo < USD 0,05 por alerta, mostrado en la UI.

## Mapeo a la API del reto
`POST /simulacion/avanzar?dias=1` → mueve `corte` en DynamoDB y lanza Vigía · `GET /alertas?estado=` · `GET /alertas/{id}` · `POST /alertas/{id}/decision` (resume el task token) · `POST /chat` (SSE) · `GET /bitacora`.

## Riesgos
1. Cold start Lambda con DuckDB (~1-2 s): provisioned concurrency de 1 solo para la demo, o mantener `/health` caliente.
2. Streaming SSE: Lambda Function URL con `RESPONSE_STREAM` (API GW HTTP API no hace streaming real).
3. Cuotas Bedrock: pedir acceso a modelos **hoy**, no el día del evento.
4. Portar vistas Postgres → DuckDB: validar contra Postgres local (docker) una vez para comprobar paridad de cifras.
