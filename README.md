# Centinela · Hackatón By Paseo (Business AI School · On Business)

Sistema de agentes de IA de vigilancia operacional y financiera para **Distribuidora Andina S.A.S.** (≈270 mil registros, 12 meses, ≈ $23.500 M COP en ventas netas). Detecta anomalías antes de que generen pérdidas, investiga la causa raíz cruzando datos y políticas en PDF, propone acciones cuantificadas en pesos y permite ejecutarlas solo con aprobación humana y bitácora inmutable.

---

## Principios y flujo de agentes
1. **Regla de oro:** los números los calcula código determinista (Python/SQL sobre DuckDB). El modelo (Claude Haiku 4.5 en Bedrock) razona, contrasta políticas y redacta; nunca inventa cifras.
2. **Flujo:** `Vigía (DuckDB)` → `Analista (Haiku + Knowledge Base)` → `Estratega (Haiku + cálculo en Python)` → **⏸ Humano (aprobar / editar / rechazar)** → `Ejecutor (borradores + bitácora)`.
3. **Privacidad:** las herramientas entregan IDs (V03, C0496), no nombres de personas; Bedrock Guardrails anonimiza PII como segunda capa.

## Stack (100 % serverless AWS, región `us-east-1`)
- **Frontend:** React + Vite + Tailwind + shadcn/ui + Recharts en **AWS Amplify Hosting**.
- **Backend:** FastAPI en **una Lambda contenedor** con AWS Lambda Web Adapter, expuesta por **Function URL** con streaming (SSE). El pipeline de agentes corre asíncrono.
- **Orquestación:** **LangGraph** con `interrupt()` y checkpoints en DynamoDB.
- **IA:** **Amazon Bedrock**, modelo `us.anthropic.claude-haiku-4-5-20251001-v1:0`, **Knowledge Base** con los 3 PDFs en S3 + **S3 Vectors** + Titan Embeddings V2, y **Guardrails** (PII + ataques de prompt).
- **Datos:** **DuckDB** (`centinela.duckdb` en la imagen, solo lectura) con las 7 vistas parametrizadas por `corte`.
- **Herramientas:** **FastMCP** in-process (`consultar_vista`, `buscar_politica`, `calcular_impacto`, `crear_borrador`).
- **Persistencia y auditoría:** **DynamoDB** (alertas, bitácora con SHA-256 encadenado, checkpoints, trazas de costo).
- **Contratos:** **Pydantic v2** en todas las fronteras (API, herramientas, LLM, persistencia).
- **Monitorización:** **CloudWatch** (logs JSON, métricas EMF, GenAI observability), Bedrock invocation logging, X-Ray, tabla de trazas con costo por alerta y **promptfoo** para pruebas; Langfuse/LangSmith descartados en el MVP.
- **IaC:** **Terraform**.

## Estructura del monorepo (planificada; hoy solo existen `docs/`, `Kit_Equipos/` y los `.md`)
```
Centinela/
├── backend/            # api/, agents/, semantic/, tools/
├── frontend/           # React + Vite (Amplify)
├── infra/              # Terraform
├── evals/              # EJ-01 SQL, EJ-02 alertas, EJ-03 seguridad, multi-semilla
├── docs/               # documentación por área
├── Kit_Equipos/        # kit oficial (CSV, SQL, políticas, generador)
├── plan_centinela_hackathon.md
├── global_tasks.md
└── ideas_creativas.md
```

## Mapa de documentación
| Documento | Descripción |
|---|---|
| [docs/01_negocio.md](docs/01_negocio.md) | 6 KPIs, políticas y escenarios S1-S6 con cifras verificadas (sin pedidos cancelados). |
| [docs/02_arquitectura_aws.md](docs/02_arquitectura_aws.md) | Arquitectura, decisiones, seguridad (Guardrails/PII), riesgos y costos. |
| [docs/03_contratos_datos.md](docs/03_contratos_datos.md) | Contratos Pydantic, handshakes H1-H10, claves de DynamoDB. |
| [docs/04_diagramas.md](docs/04_diagramas.md) | Diagramas Mermaid: arquitectura, flujo ida y vuelta (S1), estados, linaje de cifras. |
| [docs/05_monitorizacion.md](docs/05_monitorizacion.md) | Observabilidad nativa AWS, métricas, alarmas y evaluación continua. |
| [plan_centinela_hackathon.md](plan_centinela_hackathon.md) | Plan de implementación, decisiones aprobadas y plan de verificación. |
| [global_tasks.md](global_tasks.md) | Roadmap por fases; backtest y explorador de cola larga como opcionales al final. |
| [ideas_creativas.md](ideas_creativas.md) | Diferenciadores e ideas por prioridad. |
| [docs/fuente_pdf_reto.txt](docs/fuente_pdf_reto.txt) | Texto extraído del PDF del reto y de las 3 políticas. |
| [Kit_Equipos/](Kit_Equipos/) | Datos brutos, capa semántica SQL, generador y plantilla de evaluaciones. |

## Comandos
```bash
# entorno (los comandos de backend/ y frontend/ aplican cuando existan esas carpetas)
uv venv && .venv\Scripts\activate
cd backend && uv pip install -e . && uv run uvicorn api.main:app --reload --port 8000
cd ../frontend && npm install && npm run dev
cd .. && uv run pytest evals/

# dataset alternativo para pruebas de generalización (S1-S5)
set SEMILLA=12 && uv run python Kit_Equipos/generador/generar_dataset.py
```

## Herramientas AWS en desarrollo
- AWS CLI v2 con credenciales de administrador (cuenta `295894327291`, `us-east-1`).
- `.mcp.json` (en `.gitignore`) con `aws-api` (solo lectura) y `aws-docs`, instalados con `pip` en `C:\Users\sergi\.venvs\aws-mcp` porque `uvx` falla con `pywin32` en Windows.
- Conector remoto "AWS MCP" de claude.ai: requiere autenticarlo manualmente (`/mcp`).

## Estado
- **Fase 0 (Preparación):** Completada. Monorepo configurado, contratos Pydantic v2 inmutables, Bedrock verificado.
- **Fase 1A (Datos y Capa Semántica):** `centinela.duckdb` con 15 tablas oficiales, 7 vistas temporales parametrizadas por `fecha_corte()`, suite EJ-01 pasando.
- **Fase 1B (Herramientas FastMCP):** `consultar_vista` con validador estricto anti-inyección y lista blanca de columnas/vistas, y `calcular_impacto` determinista para los 6 escenarios implementados en `backend/tools/`.
- **Fase 1C (Agente Vigía):** `agents.vigia` determinista (sin LLM) con reglas para los 6 KPIs + S6, estadística de apoyo con z-score robusto (MAD), deduplicación por `huella_causa` y suite EJ-02 pasando al 100%. Corte inicial limpio identificado en `2026-06-18`.
- **Fase 1D & Infraestructura Base (Tareas 0.15, 1.6, 1.11, 1.13):**
  - **DynamoDB:** 6 tablas creadas en modo `PAY_PER_REQUEST` (`centinela_alertas` con GSIs `gsi_estado` y `gsi_huella`, `centinela_bitacora` inmutable con hash SHA-256, `centinela_checkpoints`, `centinela_trazas` con TTL 30d, `centinela_reloj` y `centinela_config`).
  - **ECR & Docker:** Repositorio `centinela-backend` con escaneo de vulnerabilidades y ciclo de vida de retención. Dockerfile optimizado con AWS Lambda Web Adapter (`RESPONSE_STREAM`) y `ENTRYPOINT` hacia Uvicorn.
  - **AWS Lambda & Function URL:** Función `centinela-backend` desplegada con Function URL pública con soporte nativo de Streaming SSE verificado en vivo (`curl -N`).
  - **API FastAPI & Persistencia:** Endpoints operativos `/health`, `/stream`, `/simulacion/corte`, `/simulacion/avanzar`, `/simulacion/reiniciar`, `/alertas` (con resolución determinista de nombres legibles PII-segregated) y `/bitacora/{alerta_id}` con verificación criptográfica.
  - **Pruebas:** 44 de 44 tests pasando (100% en `evals/`).


