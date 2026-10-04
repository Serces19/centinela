# Centinela · Hackatón By Paseo (Business AI School · On Business)

Sistema de agentes de IA de vigilancia operacional y financiera para **Distribuidora Andina S.A.S.** (≈ 270 mil registros, 12 meses, ≈ $23.500 M COP en ventas netas). Detecta desviaciones antes de que cuesten dinero, investiga la causa cruzando datos y políticas en PDF, propone acciones cuantificadas en pesos y solo las ejecuta (como borrador) con aprobación humana y bitácora inmutable.

## Principios
1. **El código calcula, el modelo explica.** Cada cifra viene de una consulta SQL registrada sobre DuckDB (SQL, filas y hash visibles); el modelo cita cifras con marcadores `{c1}` y el servidor pone los valores.
2. **Flujo:** `Vigía (reglas sobre DuckDB)` → `Analista (Haiku + KB de políticas)` → `Estratega (playbook en código + Haiku elige)` → **humano: aprobar / editar / rechazar** → `Ejecutor (borradores + bitácora)`. Rechazar enseña: la próxima propuesta del mismo tipo de causa lo tiene en cuenta.
3. **Una alerta por causa**, ordenada por dinero en riesgo sin doble conteo.
4. **Privacidad:** los agentes ven IDs (V03, C0496), no nombres; Bedrock Guardrails como segunda capa.

## Stack (serverless AWS, `us-east-1`)
Amplify (React + Vite + Tailwind + Recharts) · Lambda contenedor (FastAPI + Lambda Web Adapter) con Function URL y SSE · DuckDB en la imagen · Bedrock Claude Haiku 4.5 + Knowledge Base (S3 + S3 Vectors + Titan V2) + Guardrails · DynamoDB (alertas, bitácora, trazas, reloj, config) · CloudWatch (EMF, dashboard, alarmas) · Terraform · Pydantic v2 en todas las fronteras. Detalle en [docs/02_arquitectura.md](docs/02_arquitectura.md).

## Mapa de documentación
| Documento | Contenido |
|---|---|
| [docs/01_negocio.md](docs/01_negocio.md) | KPIs, políticas, escenarios S1–S6 con cifras verificadas. |
| [docs/02_arquitectura.md](docs/02_arquitectura.md) | Componentes, máquina de estados, flujo, seguridad, monitorización, costos medidos, desarrollo local. |
| [docs/03_contratos_datos.md](docs/03_contratos_datos.md) | Reglas de contratos, mapa de `backend/contracts/`, API, tablas DynamoDB. |
| [docs/04_evaluacion_y_demo.md](docs/04_evaluacion_y_demo.md) | Evidencia medida, criterios honestos, guion de demo, pitch y preguntas difíciles. |
| [docs/05_auditoria.md](docs/05_auditoria.md) | Auditoría contra el PDF del reto y estado final. |
| [docs/informes/](docs/informes/) | Informes **generados** por scripts (evaluación del jurado, backtest, cola larga S6); no se editan a mano. |
| [docs/fuente_pdf_reto.txt](docs/fuente_pdf_reto.txt) | Texto del PDF del reto y de las 3 políticas. |
| [global_tasks.md](global_tasks.md) | Roadmap detallado (Fase R = remediación final). |
| [plan_centinela_hackathon.md](plan_centinela_hackathon.md) | Plan original (histórico). |
| [ideas_creativas.md](ideas_creativas.md) | Ideas por prioridad. |
| [Kit_Equipos/](Kit_Equipos/) | Datos, capa semántica SQL, generador y políticas del kit oficial. |

## Estructura
```
backend/   api/ (FastAPI) · agents/ (vigia, analista, estratega, pipeline, playbook, evidencia) · services/ · tools/ · contracts/ · semantic/
frontend/  React + Vite (Amplify)
infra/     Terraform
evals/     pytest: contratos, API, agentes, chat, EJ-01/02/03, multi-semilla (+ promptfoo.yaml)
scripts/   despliegue, datos, backtest, evaluación del jurado
docs/      documentación (ver mapa)
```

## Comandos
```bash
# backend local (sin AWS: memoria + auth desactivada) — puerto 9100 porque Windows reserva 8000/8765
cd backend && uv venv && .venv\Scripts\activate && uv pip install -e .
set CENTINELA_PERSISTENCIA_BACKEND=memory && set CENTINELA_AUTH_DISABLED=true && uv run uvicorn api.main:app --port 9100

# frontend (frontend/.env.development.local: VITE_API_URL=http://localhost:9100)
cd frontend && npm install && npm run dev

# pruebas e informes
uv run pytest evals/
python scripts/ejecutar_evaluacion_jurado.py     # docs/informes/evaluacion_jurado.md
python scripts/backtest_simulado.py              # docs/informes/backtest.md

# generalización con otra semilla
set SEMILLA=12 && uv run python Kit_Equipos/generador/generar_dataset.py

# despliegue (Terraform → imagen → Lambda → Amplify)
python scripts/deploy_all.py
```
Las pruebas de agentes y chat llaman a Bedrock real: requieren credenciales AWS y `.env` con `KNOWLEDGE_BASE_ID`.

## Estado
Backend, frontend, infraestructura y base de conocimiento implementados; remediación final en curso (Fase R de [global_tasks.md](global_tasks.md)). El estado de cada requisito del PDF y la evidencia están en [docs/05_auditoria.md](docs/05_auditoria.md).
