# Centinela · Hackatón By Paseo (Business AI School · On Business)

Sistema de agentes de IA que vigila los datos de **Distribuidora Andina S.A.S.** (sintética), detecta problemas antes de que cuesten dinero, explica la causa con evidencia y propone acciones que solo se ejecutan con aprobación humana.

**Agentes:** Vigía (detecta) → Analista (causa raíz + políticas) → Estratega (1-3 acciones con $ y confianza) → ⏸ Humano → Ejecutor (borradores + bitácora).
**Regla de oro:** los números los calcula SQL/Python; el LLM nunca inventa cifras.
**Stack:** AWS serverless (Lambda, Step Functions, Bedrock, DynamoDB, S3+DuckDB/Parquet, CloudFront), Terraform, React+Vite.

## Mapa de documentación
| Doc | Contenido |
|---|---|
| [docs/01_negocio.md](docs/01_negocio.md) | KPIs, políticas, escenarios S1-S6 con entidades halladas |
| [docs/02_arquitectura_aws.md](docs/02_arquitectura_aws.md) | Arquitectura, decisiones, costos, riesgos |
| [global_tasks.md](global_tasks.md) | Roadmap detallado por día |
| [ideas_creativas.md](ideas_creativas.md) | Diferenciadores e ideas por prioridad |
| [docs/fuente_pdf_reto.txt](docs/fuente_pdf_reto.txt) | Texto extraído del PDF del reto y de las 3 políticas |
| `Kit_Equipos/` | Kit original (CSV, SQL, políticas, generador, evals) |

## Comandos
```bash
# entorno
uv venv && .venv\Scripts\activate && uv pip install duckdb pandas
# exploración rápida de datos
uv run --with duckdb --with pandas python <script>
# dataset alternativo para pruebas de generalización
set SEMILLA=11 && uv run python Kit_Equipos/generador/generar_dataset.py
```

## Estado
Fase de planificación (análisis del kit completado). Pendiente: criterios de evaluación y agenda (no incluidos en el PDF).
