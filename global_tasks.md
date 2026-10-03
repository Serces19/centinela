# global_tasks.md · Roadmap Centinela

> Nota: el PDF dice **3 días presenciales**; el equipo mencionó 2. Plan abajo para 3; si son 2, el Día 3 se funde en el cierre del Día 2 (recortar B/C de ideas).

## Hoy / antes del evento (pre-trabajo, ~1 día)
- [ ] Acceso a modelos en Bedrock (Claude grande + Haiku + Titan Embeddings) en la región elegida; verificar cuotas
- [ ] Cuenta AWS + Terraform backend (S3+lock), perfil de CLI, presupuesto/alarma USD
- [ ] Repo + estructura (`/infra`, `/api`, `/agents`, `/semantic`, `/web`, `/evals`, `/docs`) · `uv` + `.venv`
- [ ] CSV → Parquet (DuckDB) y subir a S3; portar 7 vistas a DuckDB con `corte` parametrizable
- [ ] Test de paridad de cifras: Postgres local (docker) vs DuckDB en las 7 vistas
- [ ] Repartir roles (4-5): negocio/pitch · datos+semántica · backend/agentes · frontend · infra/evals
- [ ] Leer `diccionario_de_datos.xlsx` y revisar `generar_dataset.py` (cómo se siembran S1-S5)

## Día 1 · Datos + Vigía + esqueleto (capa 1)
- [ ] Terraform: S3, DynamoDB (alertas, bitácora, feedback), Lambda api, API GW, CloudFront
- [ ] Capa semántica en Lambda (`run_sql` con validador SELECT-only sobre `v_*`) + reloj simulado
- [ ] **Vigía**: reglas de política + estadística (MAD/z, tendencia) para los 6 KPIs → detecta S1-S5 (meta: 5/5, exigido 3/5)
- [ ] Dedup por causa raíz + priorización por pesos en riesgo
- [ ] Set de evaluación inicial (`evaluaciones/`): EJ-01 preguntas SQL, EJ-02 alertas por fecha, EJ-03 inyección
- [ ] Frontend: Bandeja con alertas reales de la API (sin mocks)

## Día 2 · Analista + Estratega + aprobación (capa 2)
- [ ] Step Functions: Vigía→Analista→Estratega→⏸aprobación→Ejecutor
- [ ] Analista: causa + evidencia (consultas enlazadas) + cita de política; "no tengo evidencia suficiente" válido
- [ ] Estratega: 1-3 acciones, $ calculado en Python, confianza
- [ ] Ejecutor: borradores (correo/tarea/OC) idempotentes + bitácora con hash encadenado
- [ ] Detalle de alerta (3 niveles) · Aprobar/Editar/Rechazar con motivo
- [ ] Chat con streaming (SSE) y respuestas con cifra + fuente
- [ ] Guardrails Bedrock + etiquetado `<documento>`; prueba con política envenenada
- [ ] Backtest con reloj simulado (diferenciador 1)

## Día 3 · Pulido, evaluación y pitch (capa 3)
- [ ] Arnés multi-semilla en CI (diferenciador 2); corregir fallos de generalización
- [ ] Explorador de cola larga → escenario oculto (diferenciador B6)
- [ ] Bitácora y Configuración (umbrales, responsables, autonomía)
- [ ] Panel de costo por alerta; accesibilidad (severidad no solo color, teclado, móvil)
- [ ] `terraform apply` limpio de punta a punta; plan B: demo grabada + entorno local
- [ ] Demo 5 min (guion cronometrado) + pitch de negocio 3 min (ROI, hoja de ruta, modelo de negocio/PI, fuentes)

## Entregables a confirmar con el organizador
- [ ] Criterios de evaluación, entregables, agenda y reglas: el índice del PDF los menciona (secciones 05-07) pero el PDF solo tiene 20 láminas y termina en la sección 04. Pedirlos al organizador
- [ ] ¿El jurado usa el dataset oficial o una semilla distinta? ¿Cómo inyecta el texto malicioso?
