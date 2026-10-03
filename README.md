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
| [docs/06_informe_evaluacion_jurado.md](docs/06_informe_evaluacion_jurado.md) | Informe oficial de evaluación: 11/11 casos del jurado aprobados (100% PASSED). |
| [docs/07_guion_demo_pitch.md](docs/07_guion_demo_pitch.md) | Guion de demo cronometrada (5 min) y pitch de negocio (3 min) con matriz de defensa. |
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
- **Fase 2 (Agentes, HITL y Seguridad):** LangGraph orquestado con checkpoints en DynamoDB, Analista, Estratega, Ejecutor, Bitácora inmutable SHA-256, Chat SSE anclado y Guardrails de seguridad contra inyecciones y PII. (83 de 83 tests pasando).
- **Fase 3 (Frontend & Despliegue en AWS Amplify):** Completada.
  - **Aplicación Web SPA:** React 18 + TypeScript + Vite + Tailwind CSS v3 con UI/UX minimalista y moderna inspirada en el material de referencia (tarjetas blancas redondeadas `rounded-3xl`, fondo off-white `#f8fafc`, acentos pasteles de negocio).
  - **Control de Reloj Simulado:** Topbar interactiva con avance rápido (+1 día, +7 días, reiniciar a corte limpio `2026-06-18`).
  - **Bandeja de Decisiones (Hero 30s):** Visualización de dinero en riesgo acumulado en COP, priorización por criticidad, resolución determinista de nombres de clientes/vendedores y polling inteligente.
  - **Detalle en 3 Niveles:** Resumen ejecutivo de una frase, causa raíz con cifras trazables y políticas citadas (FIN-POL-004, COM-POL-002, OPE-POL-007), y "Cómo llegué aquí" con SQL sobre DuckDB y hash SHA-256.
  - **Human-in-the-Loop (HITL):** Aprobación con cabecera `Idempotency-Key` y previsualización de artefactos en Sandbox (`sandbox://...`), edición contextual con sliders/selectores y rechazo formal con motivo obligatorio para aprendizaje por refuerzo.
  - **Active Persona Switcher:** Alternador de rol de usuario en 1 clic (Carlos Mendoza, Ana Restrepo, David Osorio, Sergio Céspedes).
  - **Chat de Soporte Anclado:** Streaming SSE token a token en tiempo real con cifras citadas y costo en USD.
  - **Visor de Bitácora Inmutable:** Verificación matemática de la cadena SHA-256 con sello verde de integridad.
  - **Panel de Costo & ROI:** Métricas de inferencia con Claude Haiku 4.5 en Bedrock frente a capital protegido.
  - **Hosting en la Nube:** Desplegado en **AWS Amplify Hosting**: **`https://main.d1y5ytuqvgx3m2.amplifyapp.com`** (Job ID 1 - `SUCCEED`).
- **Fase 3b (Monitorización, Observabilidad y CloudWatch EMF):** Completada al 100%.
  - **Logging Estructurado JSON:** Servicio `backend/services/telemetry.py` con propagación de `x-request-id`, trazabilidad distribuida y sanitización estricta anti-PII.
  - **CloudWatch Embedded Metric Format (EMF):** Emisión asíncrona a costo marginal cero en namespace `Centinela` (`AlertasGeneradas`, `PipelineLatenciaMs`, `LlmTokensEntrada/Salida`, `CostoUsdPorAlerta`, `ValidacionFallida`, `ReintentosLlm`, `SinEvidencia`, `GuardrailIntervino`, `BitacoraCadenaRota`, `AprobacionesHumanas`, `Rechazos`).
  - **Dashboard Operativo en AWS:** Recurso `aws_cloudwatch_dashboard.operaciones` (`Centinela-Operaciones`) desplegado en `us-east-1` con widgets de severidad, latencias p50/p95, consumo de tokens, intervenciones de seguridad e integridad SHA-256.
  - **Alarmas y Notificaciones SNS:** Tópico `centinela-alarmas-operaciones` con suscripción por correo electrónico y 4 alarmas métricas (Ruptura de Bitácora, Latencia p95 > 20s, Prompt Injections y Errores Lambda).
  - **Evaluación de Seguridad promptfoo:** Configuración en `evals/promptfoo.yaml` con proveedor Bedrock Haiku 4.5 para casos EJ-03 (inyecciones de prompt, políticas adulteradas y fuga de prompt de sistema).
  - **Pipeline CI:** Workflow GitHub Actions en `.github/workflows/ci.yml` para ejecución de suite completa (`pytest`), validación de Terraform (`terraform validate`) y disparador manual de `promptfoo`.
- **Fase 4 (Evaluación, Generalización y Despliegue Maestro):** Completada al 100%.
  - **Generalización Multi-Semilla:** Validado en `evals/test_multi_semilla.py` sobre datasets sintéticos dinámicos generados con `SEMILLA=12` y `SEMILLA=42`. Detección 100% ciega y dinámica de anomalías S1 a S5 sin ninguna entidad hardcodeada (2/2 PASSED).
  - **Matriz Oficial del Jurado (EJ-01, EJ-02, EJ-03):** Ejecutado en `scripts/ejecutar_evaluacion_jurado.py` con **11 de 11 casos aprobados (100.0% PASSED)**. Reportes oficiales emitidos en `Kit_Equipos/evaluaciones/informe_casos_prueba_ejecutados.csv` y `docs/06_informe_evaluacion_jurado.md`.
  - **Orquestador de Despliegue Maestro (`scripts/deploy_all.py`):** Automatización desatendida desde cero (Terraform → S3 Políticas → Guardrail Bedrock → Docker ECR → Lambda Function URL → Amplify Hosting → E2E Healthcheck).
  - **Guion y Pitch (`docs/07_guion_demo_pitch.md`):** Demo cronometrada de 5 minutos y pitch de negocio de 3 minutos con matriz de defensa ante preguntas difíciles del jurado.
  - **Suite de Pruebas Total:** **96 / 96 tests pasando al 100%** (`uv run pytest`).


