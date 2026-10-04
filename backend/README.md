# Centinela Backend

FastAPI + Bedrock (Haiku 4.5, Knowledge Base, Guardrails) + DuckDB + DynamoDB. Sin framework de orquestación: el flujo es una máquina de estados explícita (`agents/pipeline.py`). Arquitectura, API y contratos: ver `../docs/02_arquitectura.md` y `../docs/03_contratos_datos.md`.

- `api/main.py` endpoints · `agents/` Vigía, Analista, Estratega, playbook, evidencia, pipeline · `services/` persistencia, LLM, chat, KB, guardrail, auth, umbrales · `tools/` consultas SQL y impacto · `contracts/` Pydantic · `semantic/` DuckDB y vistas.
- Local: `CENTINELA_PERSISTENCIA_BACKEND=memory CENTINELA_AUTH_DISABLED=true uv run uvicorn api.main:app --port 9100`.
