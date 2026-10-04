# global_tasks.md · Roadmap paso a paso de Centinela

Stack: AWS Lambda contenedor (FastAPI + Lambda Web Adapter, Function URL con streaming) · AWS Amplify · LangGraph · Bedrock (Claude Haiku 4.5, Knowledge Base en S3 + S3 Vectors, Guardrails) · DuckDB · DynamoDB · CloudWatch · Pydantic v2 · Terraform. Región `us-east-1`.
Documentos de apoyo: [01_negocio](docs/01_negocio.md) · [02_arquitectura](docs/02_arquitectura.md) · [03_contratos](docs/03_contratos_datos.md) · [04_diagramas](docs/02_arquitectura.md) · [05_monitorizacion](docs/02_arquitectura.md).

---

## Convenciones
- **IDs de tarea** `F.N` (fase.número) y subpasos `F.N.a`. Cada tarea termina en **Hecho cuando:** (criterio verificable).
- **Etiquetas de rol (sugeridas, a confirmar en 0.12):** `[NEG]` negocio/pitch · `[DAT]` datos y capa semántica · `[BAK]` backend y agentes · `[FRO]` frontend · `[INF]` infraestructura, evals y MLOps.
- **Entorno (Windows):** `uv venv` → `.venv\Scripts\activate` → `uv pip install …` / `uv run …`. Un script a la vez; si un comando de shell falla, se reintenta con un script Python (`pathlib`, `shutil`).
- **Datos reales siempre:** ninguna pantalla ni test usa datos inventados; todo sale de los CSV oficiales o del generador.
- **Regla de documentación:** al cerrar una tarea que cambie infraestructura, arquitectura o flujo, actualizar el `.md` correspondiente en el mismo commit.
- **Puertas de decisión (gates):** puntos con hora límite. Si no se cumplen, se pasa al plan B indicado y no se vuelve atrás.
- **Si el evento dura 2 días:** el Día 1 cubre las Fases 1-2; el Día 2 las Fases 3, 3b y 4; el opcional se descarta.

### Línea de tiempo (supuesto de 3 días)
| Bloque | Contenido | Gate de salida |
|---|---|---|
| Pre-evento | Fase 0 completa | `terraform plan` limpio y Haiku/KB accesibles |
| Día 1 mañana | Fase 1 (datos, vistas, Vigía) | Vigía detecta ≥ 3 de 5 escenarios con reloj simulado |
| Día 1 tarde | Fase 2 (A-D): KB, guardrail, Analista, Estratega | Una alerta de S1 con diagnóstico y propuesta válidos por Pydantic |
| Día 2 mañana | Fase 2 (E-H): HITL, Ejecutor, bitácora, chat; Fase 3 inicia | Flujo completo por API (curl) hasta `ejecutada` |
| Día 2 tarde | Fase 3 y 3b: UI y monitorización | Demo completa en navegador |
| Día 3 mañana | Fase 4: despliegue limpio, multi-semilla, ensayo | `terraform apply` desde cero funciona |
| Día 3 tarde | Ensayos, pitch; opcionales solo si sobra tiempo | Demo cronometrada ≤ 5 min |

---

## Fase R · Remediación de la auditoría (PRIORIDAD MÁXIMA: dejar el sistema listo para los jurados)

Origen: [docs/05_auditoria.md](docs/05_auditoria.md). Reglas de ejecución: una tarea a la vez; cada tarea termina con pruebas en verde y un commit; al terminar una tarea que cambie arquitectura o flujo se actualiza el doc correspondiente; los umbrales y las cifras salen de la política y de los datos, nunca de entidades fijas.
**Decisión de orquestación (cierra el plan B):** lo que corre en producción es una máquina de estados explícita (`procesar_alerta_completa` + `aplicar_decision_humana`), no el grafo de LangGraph, que nunca se invoca. Se elimina el grafo y el checkpointer simulado; la pausa de aprobación humana es el estado persistido `propuesta`.

- [x] **R0 · Línea base** (90 pruebas pasan, 5 fallan: todas de `test_knowledge_base`, por la KB contaminada y por la sección genérica 'Recuperado de Knowledge Base'). Ejecutar `pytest evals` completo y guardar el resultado; anotar la URL de la API y de Amplify; confirmar que `.env` no está versionado.
- [x] **R1 · Autenticación mínima (C2)** (código, pruebas y Terraform listos; el 401 en producción se verifica en R13). `[BAK]` `[INF]`
  - a. Middleware FastAPI: exige `x-api-key` en todo menos `GET /health` y `OPTIONS`; comparación en tiempo constante; 401 con `ErrorAPI`.
  - b. La clave vive en SSM Parameter Store (SecureString) y entra a la Lambda como variable por Terraform; el frontend la lee de `VITE_API_KEY` en el build.
  - c. Probar: sin clave → 401; clave errónea → 401; clave correcta → 200; el chat SSE sigue funcionando.
  - **Hecho cuando:** `curl` sin clave a `/alertas`, `/chat` y `/simulacion/reiniciar` devuelve 401.
- [x] **R2 · Orquestación simple y sin código muerto.** `[BAK]`
  - Hecho: `agents/graph.py` pasó a `agents/pipeline.py` sin LangGraph ni checkpointer simulado (`langgraph` fuera de las dependencias, `EstadoGrafo` e `InterruptPayload` fuera de los contratos), el pipeline es idempotente por estado y la generación de borradores quedó en una sola función.
  - Los respaldos que inventan datos (`_crear_accion_fallback`, diagnóstico de respaldo) se eliminan en R7, donde se reescriben el Analista y el Estratega.
- [x] **R3 · Una alerta por causa y bandeja ordenada (C3, C4)** (backend listo y probado; la bandeja de la UI se rehace en R9). `[BAK]`
  - a. `alerta_id` estable por `huella_causa` (se crea en la primera detección y no cambia entre cortes).
  - b. `GET /alertas`: ejecuta el Vigía al corte actual, une cada hallazgo con el registro persistido por huella (estado, propuesta, versión) y devuelve valores del corte actual; las causas que ya no se detectan no se muestran.
  - c. Agrupar la cartera: un cliente = una alerta (une saldo vencido y días de pago); `dinero_en_riesgo` sin doble conteo.
  - d. El Vigía persiste en el primer `GET` o en `avanzar`, nunca un duplicado.
  - e. Endpoint de resumen: `GET /alertas/resumen` → total de dinero en riesgo (sin doble conteo), número de alertas por severidad y **las 3 decisiones clave** (mayor $ × severidad).
  - f. `POST /simulacion/reiniciar` borra alertas, propuestas, resultados, trazas y feedback de la demo (no la bitácora) y vuelve al corte limpio.
  - **Hecho cuando:** 0 huellas duplicadas en la respuesta; el total de dinero en riesgo no supera la cartera abierta; avanzar el reloj muestra S2-S5 sin quedarse con las alertas viejas.
- [x] **R3b · Consultas registradas (trazabilidad real).** `[BAK]`
  - Hecho: toda regla del Vigía y toda llamada a `consultar_vista` produce una `ConsultaRegistrada` (SQL con el corte, columnas, hasta 300 filas, hash del resultado, `consulta_id` determinista), se persiste con la alerta y se sirve en `GET /consultas/{id}`. Pendiente en R9: mostrarla en el nivel 3 del detalle (hoy solo se listan ids).
- [x] **R4 · Reloj que dispara de verdad (C8)** (backend: `avanzar` persiste el Vigía y devuelve `alertas_detectadas`/`alertas_nuevas`; `paso_actual` en la alerta; el encadenado del análisis en la UI va en R9). `[BAK]`
  - a. `POST /simulacion/avanzar`: mueve el corte, ejecuta y persiste el Vigía, y responde con `alertas_nuevas` (no `pipeline_disparado` falso).
  - b. Campo `paso_actual` en la alerta (`vigia`/`analista`/`estratega`/`ninguno`), actualizado por el pipeline.
  - c. La UI encadena el análisis de las 3 decisiones clave tras avanzar el reloj.
  - **Hecho cuando:** tras avanzar a 2026-08-15 aparece la alerta de S1, con paso visible y propuesta lista sin pasos manuales.
- [x] **R5 · Knowledge Base limpia (C5).** `[INF]`
  - Hecho: vector bucket e índice propios (`centinela-vectors-<cuenta>/politicas`, `scripts/provision_vectores.py`); KB nueva `centinela-politicas-kb` (id `6WKO5PZCW3`) aplicada con Terraform; una sola copia de cada política con nombre canónico; los 12 vectores huérfanos de Centinela se borraron del índice compartido (los de la otra KB no se tocaron).
  - `knowledge.py` quedó en un solo camino (KB): el documento sale de la URI de S3, se descartan resultados ajenos y duplicados, la sección se deduce de los encabezados de cada política; sin KB devuelve vacío. Se eliminó el corpus embebido, el modo híbrido y la caché de embeddings.
  - `scripts/sync_knowledge_base.py` localiza la KB por nombre, ingiere y verifica 5 consultas (solo políticas, sin duplicados). `evals/test_knowledge_base.py`: 12 pruebas pasan.
- [x] **R6 · Configuración real (C7)** (backend + UI verificados)** `[BAK]` `[FRO]`
  - a. Contrato `ConfigKpi` y tabla `centinela_config`: umbrales por KPI con sus valores por defecto tomados de `metricas.yaml` y de la política, y autonomía por tipo de acción (Informa/Propone/Ejecuta).
  - b. `GET /config` y `PUT /config` (validados).
  - c. El Vigía lee los umbrales (margen, días de mora, cobertura, descuento, intervalo, costo %) y la autonomía limita al Ejecutor (`Informa` no genera borradores).
  - d. Reescribir `ConfiguracionPanel.tsx` para leer y guardar de verdad; quitar los valores inventados.
  - **Hecho cuando:** cambiar un umbral cambia las alertas del siguiente corte y queda registrado en la bitácora; con test.
- [x] **R7 · Análisis fiel a los datos (C6, C7).** `[BAK]`
  - Hecho: el **código reúne la evidencia** (`agents/evidencia.py`: fichas con cifras de consultas registradas) y el **modelo explica** citando cifras con marcadores `{cN}`; no puede escribir números propios (dígitos ni palabras), salvo umbrales literales de la política citada (`numeros_politica`). Formato validado con Pydantic y un reintento; si el modelo falla, plantilla determinista a partir de la ficha (marcada en `supuestos`); sin datos, "sin evidencia".
  - Hecho: el **playbook** (`agents/playbook.py`) arma las acciones candidatas con parámetros reales por política (nivel de cartera por días de mora, suspensión de cotizar tras 2 semanas, ajuste de precio que repone el margen mínimo ponderado por ventas, OC a expeditar, etc.); el modelo solo elige, ordena y justifica. Sin IDs ni parámetros inventados; se eliminaron los respaldos que fabricaban datos.
  - Hecho: impacto calculado con consultas registradas y sin relleno (`tools/impacto.py`); el ajuste de precio muestra el margen que **recupera**, y la renegociación el **sobrecosto** que evita.
  - Hecho: **aprende de rechazos**: el motivo y los tipos de acción rechazados se guardan (tabla `centinela_config`, corregido el esquema de claves) y las propuestas siguientes de la misma familia de causa mandan al final lo ya rechazado y lo explican (`Propuesta.aprendizaje`). `POST /alertas/{id}/reabrir` permite volver a proponer tras un rechazo.
  - Costo medido con Bedrock (Haiku 4.5): ≈ US$ 0,008 por alerta con análisis y propuesta.
- [x] **R8 · Chat real (C1).** `[BAK]`
  - Hecho: el chat es un agente (Haiku 4.5) con herramientas `consultar_vista` (SQL parametrizado con agregados, `count(distinct)` y orden por alias) y `buscar_politica`, que responde con la herramienta `responder`: texto con marcadores `{cN}` y referencias a celdas de las consultas. **El servidor lee los valores** (`verificar_respuesta`); el modelo no escribe números (salvo umbrales literales de la política recuperada y números de nombres de producto devueltos por la consulta). Eventos SSE: `paso` (en vivo) → `token` → `cifra` → `grafico` → `fin` (consultas y costo real de Bedrock). Guardrail en la pregunta y en la respuesta; sin datos → "no tengo evidencia suficiente".
  - Hecho: se eliminó la lógica por palabras clave y `CENTINELA_BEDROCK_CHAT`; `proveedor_id` se añadió a `v_ventas` y `v_cobertura_inventario`; las consultas del chat quedan registradas y se sirven en `/consultas/{id}`.
  - Verificado con Bedrock real (9 pruebas, 3 corridas seguidas): "¿qué otros clientes compran los SKU P0001 y P0006?", "¿qué otros SKU le compramos al proveedor PR08?", la anclada a S1, política con umbral literal, gráfico con serie real, fuera de datos, inyección.
- [x] **R9 · Frontend sin entidades fijas (C3)** (verificado en navegador: bandeja, detalle, chat, rechazo→reabrir→aprendizaje, bitácora)** `[FRO]`
  - a. Borrar `clasificarEscenario`, `esAlertaEstrategica`, `esCorteInicialLimpio` y los títulos con cifras fijas; usar `GET /alertas/resumen`.
  - b. Bandeja: banner con el dinero en riesgo y las 3 decisiones clave; el resto plegado y ordenado.
  - c. Mostrar `paso_actual`; chat con gráfico; bitácora general (R10); hitos del reloj solo con fechas, sin nombres de entidades.
  - d. Revisar teclado, contraste y vista móvil.
  - **Hecho cuando:** `grep -rn "PR08\|C0496\|P0119\|V03\|C0061" frontend/src` no devuelve nada, y la bandeja con `SEMILLA=12` muestra los escenarios de esa semilla.
- [x] **R10 · Bitácora general** (backend listo; vista en R9). `[BAK]` `[FRO]` `GET /bitacora` sin `alerta_id` (paginado, filtro por actor y evento) y vista de auditoría con "quién aprobó qué y cuándo".
- [x] **R11 · Credibilidad de los documentos (C8)** (docs consolidados en 5 + informes generados; backtest y evaluación rehechos). `[NEG]` `[BAK]`
  - a. Backtest: primera detección del **escenario** (la entidad afectada con las reglas del propio escenario, no cualquier alerta de la entidad); quitar la columna "detección tradicional" supuesta o presentarla como supuesto.
  - b. Unificar el impacto de S1 con lo que calcula el sistema; calcular el costo por alerta con trazas reales (ya medidas) y derivar el ROI de ahí.
  - c. EJ-02.1 con criterio honesto: el corte limpio no tiene alertas de S1-S5; el resto del ruido se mide y se reporta.
  - d. Consolidar la documentación (de 11 a 4 archivos) y mover los informes generados a `docs/informes/`.
  - e. Reescribir el guion de demo y el pitch con las cifras medidas.
  - **Hecho cuando:** cada número del pitch tiene una consulta o una traza que lo respalda.
- [x] **R12 · Limpieza del repositorio** (scripts obsoletos eliminados, `temp_seed_*` ignorados por git, README actualizado). `[INF]` Mover o borrar scripts que no se usan, sacar `temp_seed_*` del árbol de trabajo, actualizar `README.md`.
- [ ] **R13 · Despliegue y verificación final.** `[INF]`
  - a. Reconstruir imagen, `terraform apply`, desplegar frontend.
  - b. Ejecutar toda la suite, la evaluación del jurado y `SEMILLA=12` y `42`.
  - c. Repetir en producción las 3 preguntas del chat, el flujo completo de S1 (reloj → alerta → detalle → chat → aprobar → bitácora) y la prueba de inyección.
  - d. Ensayo cronometrado de la demo (≤ 5 min).
  - **Hecho cuando:** checklist de las láminas 7, 9, 15-19 en verde con evidencia en `docs/05_auditoria.md` (§ Estado final).

---

## Fase 0 · Preparación (pre-evento)

- [x] **0.1 Análisis del kit y escenarios.** Verificados S1-S6 con DuckDB; ver [01_negocio](docs/01_negocio.md).
- [x] **0.2 Cifras corregidas** (sin pedidos cancelados, como las vistas oficiales).
- [x] **0.3 Decisiones aprobadas:** `us-east-1`, Haiku 4.5, KB en S3 con S3 Vectors, Amplify, PII con Guardrails, monitorización con CloudWatch, contratos Pydantic.
- [x] **0.4 Credenciales y Bedrock.** AWS CLI como administrador (cuenta `295894327291`); `converse` con `us.anthropic.claude-haiku-4-5-20251001-v1:0` responde; Titan Embeddings V2 disponible.
- [x] **0.5 `.mcp.json` local** con `aws-api` (solo lectura) y `aws-docs`, instalados con `pip` en `C:\Users\sergi\.venvs\aws-mcp`.
- [x] **0.6 Conector remoto "AWS MCP".** `[INF]`
  - a. Abrir `/mcp` en una terminal de Claude Code (o Conectores en la app) y autenticar "AWS MCP" con la cuenta `295894327291`.
  - b. Reiniciar la sesión para cargar `.mcp.json` y aprobar los servidores `aws-api` y `aws-docs`.
  - c. Probar `GetCallerIdentity` por el MCP y una búsqueda en `aws-docs` (por ejemplo "Lambda Web Adapter response streaming").
  - **Hecho cuando:** ambos MCP responden en una sesión nueva.
- [x] **0.7 Herramientas locales.** `[INF]`
  - a. Actualizar AWS CLI v2 (la 2.27.22 no trae `s3vectors`): `msiexec /i https://awscli.amazonaws.com/AWSCLIV2.msi`. Verificar `aws s3vectors help`.
  - b. Confirmar Terraform ≥ 1.15, Docker, Node ≥ 24 y `uv` (ya instalados). Instalar `promptfoo` más adelante con `npx`.
  - c. En el registro de Terraform, buscar la versión del provider `hashicorp/aws` que incluya `S3_VECTORS` en `aws_bedrockagent_knowledge_base` y los recursos `aws_s3vectors_*`; fijar `~>` esa versión.
  - **Hecho cuando:** `aws --version` ≥ la que incluye `s3vectors` y la versión del provider está anotada en `infra/versions.tf`.
- [x] **0.8 Estructura del monorepo.** `[INF]`
  - a. Crear carpetas `backend/{api,agents,semantic,tools,contracts}`, `frontend/`, `infra/`, `evals/`, `scripts/`.
  - b. `backend/pyproject.toml` con `uv` (Python 3.12): `fastapi`, `uvicorn`, `pydantic>=2`, `duckdb`, `boto3`, `langgraph`, `fastmcp`, `pytest`; sin `pandas` en runtime.
  - c. `uv venv` en la raíz y `.venv\Scripts\activate`; `uv pip install -e backend`.
  - d. `.env.example` con `AWS_REGION=us-east-1`, `MODEL_ID`, `CENTINELA_API_KEY` (sin valores reales).
  - **Hecho cuando:** `uv run pytest` corre (aunque haya 0 tests) y el árbol coincide con el README.
- [x] **0.9 Estado de Terraform y presupuesto.** `[INF]`
  - a. Crear bucket S3 versionado `centinela-tfstate-295894327291` y tabla DynamoDB de lock (script único en `scripts/bootstrap_tfstate.py`).
  - b. `infra/main.tf` con backend S3, provider y `default_tags { Proyecto = "centinela" }`.
  - c. `aws_budgets_budget` de 20 USD/mes con aviso al 50 % y 80 % por correo (SNS).
  - **Hecho cuando:** `terraform init` y `terraform plan` terminan sin errores.
- [x] **0.10 Rol IAM de desarrollo para Bedrock.** `[INF]`
  - a. Documentar el permiso mínimo de la Lambda: `bedrock:InvokeModel`, `InvokeModelWithResponseStream`, `Converse`, `ConverseStream`, `ApplyGuardrail`, `Retrieve`.
  - b. Recursos: el **perfil de inferencia** `us.anthropic.claude-haiku-4-5-…` **y** los ARN `foundation-model/anthropic.claude-haiku-4-5-…` de las regiones que cubre el perfil (un perfil `us.` enruta a varias regiones; con solo el ARN del perfil falla).
  - **Hecho cuando:** un `converse` desde un rol de prueba con ese permiso responde.
- [ ] **0.11 Confirmaciones con organizadores.** `[NEG]`
  - a. Duración: ¿2 o 3 días?
  - b. Pedir las láminas 05 (metodología y agenda), 06 (evaluación: criterios y pruebas del jurado) y 07 (comercialización).
  - c. Preguntar si el jurado usa el dataset oficial o una semilla distinta, y cómo inyecta el texto malicioso (¿PDF nuevo, texto en una política?).
  - d. Pasar los criterios a `docs/00_criterios_evaluacion.md` y ajustar prioridades.
  - **Hecho cuando:** hay respuesta escrita para a-c.
- [ ] **0.12 Roles del equipo (4-5 personas).** `[NEG]`
  - a. Asignar `[NEG]`, `[DAT]`, `[BAK]`, `[FRO]`, `[INF]` por nombre y anotarlos en el README.
  - b. Acordar canal de comunicación, rama `main` protegida, un commit por tarea y convención de nombres de rama.
  - **Hecho cuando:** cada tarea tiene dueño.
- [x] **0.13 Completar contratos faltantes.** `[BAK]`
  - Faltan en [03_contratos](docs/03_contratos_datos.md): `SimulacionResp`, `AlertaVista` (Alerta + nombres resueltos para la UI), `ConfigKpi` (umbral, responsable, autonomía por tipo de acción) y la tabla `centinela_config`.
  - **Hecho cuando:** los cuatro existen en el doc, con prueba, y están en `backend/contracts/`.
- [x] **0.14 Contratos Pydantic en código.** `[BAK]`
  - a. Copiar los bloques de `docs/03_contratos_datos.md` a `backend/contracts/{base,evidencia,alertas,agentes,decision,bitacora,operacion,herramientas}.py`.
  - b. Mover las pruebas verificadas a `evals/test_contratos.py` (IDs, transiciones, unión discriminada, `DecisionRequest`, `numeros_sueltos`, cadena de bitácora y manipulación).
  - **Hecho cuando:** `uv run pytest evals/test_contratos.py` pasa.
- [x] **0.15 Prueba de humo de Lambda contenedor.** `[INF]` *(reduce el mayor riesgo técnico)*
  - a. `backend/Dockerfile` basado en `public.ecr.aws/lambda/python:3.12` con el Lambda Web Adapter (`/opt/extensions/lambda-adapter`), `AWS_LWA_INVOKE_MODE=response_stream`, `PORT=8080` y `ENTRYPOINT ["python", "-m", "uvicorn"]`.
  - b. FastAPI mínima en `backend/api/main.py` con `GET /health` y un endpoint SSE `GET /stream` que emite 5 eventos en tiempo real.
  - c. `infra/lambda.tf`: ECR `centinela-backend`, función Lambda `centinela-backend` con package type Image, Function URL con `invoke_mode = "RESPONSE_STREAM"`, `authorization_type = "NONE"` y permisos `lambda:InvokeFunctionUrl` y `lambda:InvokeFunction`.
  - d. Probado con `curl -N`: los 5 eventos SSE llegan en streaming con intervalos de 0.5 s sin buffering.
  - e. Invocación directa y asíncrona verificada entregando eventos JSON al runtime.
  - **Hecho cuando:** SSE llega en streaming y el endpoint `/health` responde 200 en la nube.


---

## Fase 1 · Datos, capa semántica y Vigía (Día 1 mañana)

### 1A. Datos y vistas en DuckDB `[DAT]`
- [x] **1.1 Construir `centinela.duckdb`.**
  - a. `scripts/build_duckdb.py`: leer los 15 CSV de `Kit_Equipos/datos/csv` con tipos explícitos (fechas `DATE`, importes `DECIMAL(16,2)`/`BIGINT`) y crear las tablas con las claves y los índices de `01_esquema.sql`.
  - b. Verificar los conteos contra `Kit_Equipos/README.md`: pedidos 20.013, detalle 60.103, facturas 19.085, pagos 17.010, inventario 146.000.
  - c. Guardar el archivo en `backend/semantic/centinela.duckdb` (se hornea en la imagen; no se versiona si pesa > 50 MB, se genera en el build).
  - **Hecho cuando:** los conteos coinciden y el archivo abre en modo `read_only=True`.
- [x] **1.2 Reloj simulado en las vistas.**
  - a. Decisión: tablas persistidas en el `.duckdb` de solo lectura; las **vistas y la macro `fecha_corte()` se crean en memoria al abrir cada conexión** (`ATTACH … (READ_ONLY)` + `CREATE TEMP VIEW`), con el `corte` guardado en una tabla temporal de una fila. Evita escribir en un archivo de solo lectura.
  - b. `backend/semantic/views.sql` con las 7 vistas portadas de `Kit_Equipos/datos/sql/03_capa_semantica.sql`, cambiando `date_trunc`, tipos y casts a la sintaxis de DuckDB.
  - c. Filtrar por `corte` **todas** las vistas: facturas con `fecha_factura <= corte`, pagos con `fecha_pago <= corte`, pedidos con `fecha <= corte`, inventario con `fecha <= corte`, y precios/costos con la vigencia máxima `<= corte`.
  - d. Trampas de datos a resolver y documentar:
    - `estado` de un pedido es el **final**, no histórico: para cobertura a un corte pasado, `unidades_pendientes` solo es fiable cerca del cierre. Para S3 usar OC retrasada derivada: `fecha_esperada < corte` y (`fecha_recibida` nulo o `> corte`).
    - Pedidos cancelados siempre excluidos (como `v_ventas`).
    - Mapeo ciudad → bodega está fijo en la vista de cobertura; moverlo a una tabla de referencia.
  - **Hecho cuando:** con `corte = 2026-09-30` las 7 vistas devuelven las mismas filas que el SQL original.
- [ ] **1.3 Paridad con Postgres.**
  - a. `docker run` de Postgres, ejecutar `01_esquema.sql`, `02_carga.sql`, `03_capa_semantica.sql`.
  - b. Comparar con DuckDB, para `corte = 2026-09-30` y otros dos cortes, las 7 vistas: conteo de filas y sumas de columnas numéricas.
  - **Hecho cuando:** diferencias = 0 (o explicadas por redondeo ≤ 0,1 pp).
- [x] **1.4 Pruebas de las cifras de los escenarios (EJ-01).** `[DAT]`
  - a. `evals/test_ej01_sql.py` con los valores ya verificados: S4 = 316 líneas y $8.096.844; S5 = última compra 2026-07-09 y 43 pedidos; S6 = 116 líneas y $2.721.412; impacto de S1 = $23.558.346/mes (corte 2026-08-15, unidades de 30 días × aumento de costo).
  - b. Añadir 3 preguntas tipo jurado (margen de una línea en un mes, saldo vencido de un cliente, cobertura de un SKU).
  - **Hecho cuando:** pasan contra las vistas con el corte correspondiente.

### 1B. Herramientas y reloj `[BAK]`
- [x] **1.5 `consultar_vista` con validador.**
  - a. `ConsultarVistaIn` → SQL parametrizado (nunca texto libre): lista blanca de vistas `v_*` y de columnas por vista, operadores permitidos, `LIMIT` ≤ 500 forzado.
  - b. Devolver `ConsultaRegistrada` (SQL renderizado, corte, filas, hash del resultado) y guardarla en `trazas`.
  - c. Tests: rechaza tablas crudas, `;`, subconsultas, columnas fuera de lista y límites > 500.
  - **Hecho cuando:** los intentos maliciosos fallan con `ErrorAPI(validacion)`. Implementado en `backend/tools/consultas.py` y probado en `evals/test_consultar_vista.py`.
- [x] **1.6 Reloj simulado.**
  - a. Tabla `centinela_reloj` (`RELOJ`/`ACTUAL`) desplegada en DynamoDB con `{corte, run_id, actualizado_en}`; estado inicial configurable en `CORTE_INICIAL_LIMPIO` (`2026-06-18`).
  - b. `POST /simulacion/avanzar?dias=n` (1 ≤ n ≤ 365): valida que no pase de `2026-09-30`, guarda el nuevo corte, responde `SimulacionResp` y dispara el pipeline asíncrono.
  - c. `GET /simulacion/corte` devuelve el corte actual y los límites; `POST /simulacion/reiniciar` vuelve al inicio limpio (`2026-06-18`).
  - **Hecho cuando:** avanzar el reloj cambia el corte y los límites se respetan estrictamente (probado en `evals/test_api.py` y verificado en vivo por Function URL).

### 1C. Vigía `[BAK]` + `[DAT]`
- [x] **1.7 Reglas por KPI** (código determinista en `agents/vigia.py`, umbrales desde `metricas.yaml` y la política; cada regla devuelve `Hallazgo`).
  - a. **Costo/margen (S1):** costo de proveedor +5 % (OPE-POL-007) y caída de margen > 3 pp frente al promedio de 8 semanas, o margen bajo el mínimo de la línea. S1 se detecta primero por costo el 2026-08-15.
  - b. **Saldo vencido (S2):** `max_dias_vencido > 15` o `saldo_abierto > cupo`; nivel de escalamiento según FIN-POL-004 (1-15, 16-30, 31-60, > 60).
  - c. **Días de pago (S2):** aumento > 50 % frente al histórico del cliente.
  - d. **Cobertura (S3):** < 10 días en clase A (7 B, 5 C); crítico < 5 días con pedidos pendientes u OC retrasada.
  - e. **Descuento en exceso (S4):** cualquier línea sobre el tope sin aprobación; agrupar por vendedor y semana; regla de dos semanas consecutivas (COM-POL-002 §5).
  - f. **Intervalo de compra (S5):** > 3× el intervalo habitual con ≥ 10 pedidos.
  - g. **Venta bajo costo (S6):** líneas con precio neto < costo, agrupadas por SKU.
  - **Hecho cuando:** cada regla tiene su prueba unitaria con una entidad real del dataset oficial.
- [x] **1.8 Estadística de apoyo.** z-score robusto (MAD) y tendencia sobre margen semanal y días de pago; sirve como segunda señal, no reemplaza las reglas de política.
  - **Hecho cuando:** hay un test que marca la caída de margen de Hogar con z-score aunque el umbral de política no se use (`test_estadistica_apoyo_zscore_hogar` en `evals/test_ej02_alertas.py`).
- [x] **1.9 Dinero en riesgo por tipo (`calcular_impacto`).** Fórmulas documentadas en el docstring y en `01_negocio.md`:
  - S1: unidades de 30 días × aumento de costo; S2: saldo vencido (y saldo abierto en riesgo); S3: demanda diaria × precio de lista × días hasta reposición; S4: suma de `descuento_en_exceso`; S5: ventas promedio mensuales del cliente (90 días); S6: pérdida directa por línea.
  - **Hecho cuando:** S1 reproduce $23.558.346 y S4 $8.096.844. Implementado en `backend/tools/impacto.py` y probado en `evals/test_calcular_impacto.py`.
- [x] **1.10 Deduplicación y prioridad.** `huella_causa` = `kpi|entidad raíz` (S1 → `costo|PR08`, no 4 alertas por SKU); una alerta abierta por huella (no se reabre mientras esté en `propuesta`); orden por `dinero_en_riesgo_cop` descendente; severidad por reglas (crítica / alta / media / baja).
  - **Hecho cuando:** S1 produce una sola alerta con 4 SKU (`test_deduplicacion_y_prioridad_s1`).
- [x] **1.11 Persistencia de alertas y bitácora inicial.** Crear `Alerta` (estado `nueva`) con `PutItem` condicional y sellar `alerta_creada` en la bitácora (`backend/services/persistencia.py`).
  - **Hecho cuando:** reejecutar el Vigía con el mismo corte no duplica alertas (probado en `evals/test_api.py::test_idempotencia_persistencia_alertas`).
- [x] **1.12 Prueba de detección (EJ-02).** `evals/test_ej02_alertas.py`
  - a. Con `corte = 2026-09-30`: aparecen S1 (PR08), S2 (C0496), S3 (P0119, BOD-MDE), S4 (V03), S5 (C0061), con la entidad exacta.
  - b. Con `corte = 2026-08-15`: aparece S1.
  - c. Con `corte = 2026-06-30`: no aparecen S1, S3 ni S5 (el costo sube el 08-15, la OC se retrasa en agosto y C0061 compra hasta el 07-09). S2 sí aparece (C0496 superó 15d el 2026-06-20); S4 no aparece (comienza el 2026-07-01).
  - d. Determinado el **corte inicial limpio**: `2026-06-18` (guardado en `contracts.configuracion.CORTE_INICIAL_LIMPIO`).
  - **Hecho cuando:** 5 de 5 en `2026-09-30` (el reto exige 3 de 5) y el corte inicial limpio está anotado. Probado en `evals/test_ej02_alertas.py`.
- [x] **1.13 Infraestructura base.** `[INF]` `infra/dynamodb.tf` con las 6 tablas (`alertas` con GSIs `gsi_estado` y `gsi_huella`, `bitacora`, `checkpoints`, `trazas` con TTL 30 días, `reloj` y `config`); ECR `centinela-backend` y Lambda `centinela-backend` con Lambda Web Adapter desplegados mediante Terraform.
  - **Hecho cuando:** `terraform apply` crea todo y la API responde `/health` y `/stream` SSE en la nube (Function URL activa).
- **GATE día 1 mediodía:** Vigía en la nube detecta ≥ 3 de 5 escenarios (5 de 5 verificados). Superado con éxito.

---

## Fase 2 · Analista, Estratega, seguridad y aprobación humana (Día 1 tarde - Día 2 mañana)

### 2A. Conocimiento y seguridad `[INF]`
- [x] **2.1 Knowledge Base y Recuperación Semántica.**
  - a. Bucket S3 versionado y cifrado AES256 `centinela-politicas-295894327291` en `us-east-1` creado con los 3 PDFs normativos (`FIN-POL-004`, `COM-POL-002`, `OPE-POL-007`) vía `scripts/setup_s3_politicas.py`.
  - b. Servicio `PoliticasRetriever` en `backend/services/knowledge.py` con chunking de ~300 tokens por sección explícita, embeddings Bedrock Titan V2 (`amazon.titan-embed-text-v2:0`, 1024 dim), similitud coseno, caché local persistido y fallback a Bedrock Knowledge Base.
  - c. Evaluado en `evals/test_knowledge_base.py` con 5 preguntas clave verificadas al 100%: "plazo mayoristas" (FIN-POL-004 §2), "tope descuento minoristas" (COM-POL-002 §2), "cobertura mínima clase A" (OPE-POL-007 §2), "costo sube más del 5 %" (OPE-POL-007 §4) y "más de 60 días vencido" (FIN-POL-004 §4).
  - d. Infraestructura como Código: Aprovisionamiento formal en Terraform (`infra/kb.tf`) con Bedrock Knowledge Base S3 Vectors (`OGWCO3WVFH`), Data Source S3 (`BHCVMHRB2F`), roles IAM de ejecución e inyección automática en la Lambda backend. Ingestión ejecutada y verificada.
  - **Hecho cuando:** cada pregunta devuelve el fragmento de política correcto con documento y sección. Verificado al 100%.
- [x] **2.2 Guardrail `centinela-guardrail`.**
  - a. Creado y publicado en AWS Bedrock (`scripts/setup_guardrail.py`): Guardrail ID `zuonkeflxh8f`, versión `1`.
  - b. Filtro PII: `NAME`, `EMAIL`, `PHONE`, `ADDRESS` con acción `ANONYMIZE`.
  - c. Filtro de ataques de prompt (`PROMPT_ATTACK`) con fuerza `HIGH` en la entrada y capa de defensa en profundidad local.
  - d. Servicio `backend/services/guardrail.py` con `aplicar_guardrail(texto, fuente)` y tests en `evals/test_guardrail.py` verificando anonimización PII y neutralización de prompt injections en español e inglés.
  - **Hecho cuando:** texto con PII sale anonimizado y prompt attack es marcado con `GUARDRAIL_INTERVENED`. Verificado al 100%.
- [x] **2.3 Capa determinista de PII.** `[BAK]`
  - a. Las herramientas y el Vigía operan exclusivamente sobre IDs técnicos (`V03`, `C0496`, `PR08`).
  - b. La resolución de nombres se segrega a `backend/services/resolucion.py` (`resolver_nombres`) para uso exclusivo de la UI (`AlertaVista`).
  - c. Verificado en `evals/test_pii_determinista.py`: cero filtraciones de nombres de `vendedores.csv` en Hallazgos o alertas.
  - **Hecho cuando:** la búsqueda de nombres de vendedor en los prompts/hallazgos da 0 resultados. Verificado al 100%.
- [x] **2.4 Herramienta FastMCP `buscar_politica`.** `[BAK]`
  - a. Implementada en `backend/tools/politicas.py` (`BuscarPoliticaIn` → `BuscarPoliticaOut`).
  - b. Recupera fragmentos con `PoliticasRetriever`, evalúa cada fragmento con `aplicar_guardrail`, calcula `fragmento_hash` SHA-256 canónico.
  - c. Detección de políticas envenenadas (escenario EJ-03): si un fragmento contiene instrucciones maliciosas, activa `guardrail_ataque_detectado = True`.
  - d. Registrada como `@mcp.tool(name="buscar_politica")` y evaluada en `evals/test_buscar_politica.py`.
  - **Hecho cuando:** un fragmento envenenado (EJ-03) activa `guardrail_ataque_detectado`. Verificado al 100%.

### 2B. Analista `[BAK]`
- [x] **2.5 Prompt de sistema y `emitir_diagnostico`.**
  - a. Prompt: rol, delimitadores `<datos_politica>`, reglas de citas estrictas, cifras trazables a `consulta_id` en `cifras`, conteos con letras (`_limpiar_numeros_sueltos`), sanitización de longitudes de resumen (≤ 220) y causa raíz (≤ 800).
  - b. Herramienta `emitir_diagnostico` basada en `DiagnosticoLLM`.
  - c. Bucle con Bedrock Converse Tool Use (Haiku 4.5), hasta 6 llamadas a herramientas (`consultar_vista`, `buscar_politica`, `emitir_diagnostico`).
  - d. Manejo de errores y reintentos, con fallback `sin_evidencia` si no se cumplen requisitos.
  - e. Registro de `TrazaLLM` (tokens de entrada/salida, latencia ms, costo USD y modelo).
  - **Hecho cuando:** S1 produce diagnóstico estructurado citando `OPE-POL-007` y cifras trazables a consultas reales (probado en `evals/test_fase2_agentes.py`).
- [x] **2.6 Cálculo de costo USD.** Tarifas vigentes de Haiku 4.5 ($1.00 / M tokens entrada, $5.00 / M tokens salida) integradas en `backend/agents/analista.py` y `backend/services/persistencia.py` (`guardar_traza`).
  - **Hecho cuando:** cada invocación registra tokens y costo exacto en `centinela_trazas` con TTL 30 días.

### 2C. Estratega `[BAK]`
- [x] **2.7 `emitir_propuesta`.** Modelo genera `PropuestaLLM` a partir de lista cerrada de acciones tipadas (`ajuste_precio`, `contacto_cartera`, `expeditar_oc`, `revision_descuentos`, `reactivar_cliente`, `corregir_venta_bajo_costo`) sin cifras inventadas.
- [x] **2.8 `calcular_impacto`.** Servidor calcula deterministamente `ImpactoCalculado` con `calcular_impacto_economico` para cada acción y construye `Propuesta` con `AccionId`.
  - **Hecho cuando:** S1 produce propuesta de ajuste de precio con impacto económico exacto ($23.558.346/mes) y nivel de confianza.
- [x] **2.9 Reglas de coherencia.** `_filtrar_acciones_coherentes` aplica deduplicación por tipo y validación estricta de SKU, clientes y órdenes contra los hallazgos de la alerta, descartando acciones alucinadas o espurias.

### 2D. Orquestación y aprobación `[BAK]`
- [x] **2.10 Grafo LangGraph.**
  - a. `backend/agents/graph.py` con `EstadoGrafo`, nodos `vigia -> analista -> estratega -> aprobacion_humana -> ejecutor`.
  - b. Checkpointer `DynamoDBSaver` respaldado por `centinela_checkpoints` con `thread_id = alerta_id`.
  - c. Suspensión Human-in-the-Loop mediante `interrupt(InterruptPayload)` y reanudación con `Command(resume=decision_req)`.
  - d. Sellado de bitácora criptográfica inmutable en cada transición de nodo (`EntradaBitacora.sellar`).
  - **Hecho cuando:** alerta pasa de `nueva -> en_analisis -> propuesta`, se suspende en `aprobacion_humana` y se reanuda a `aprobada -> ejecutor -> ejecutada` (probado en `evals/test_fase2_agentes.py`).
- [ ] **2.11 Invocación asíncrona (H2).** `/simulacion/avanzar` y `/decision` invocan la Lambda con `InvocationType=Event`; el adaptador entrega `PipelineEvent` al endpoint interno; SQS DLQ con 2 reintentos. Idempotencia por `(run_id, alerta_id)`.
  - **Hecho cuando:** un fallo forzado llega a la DLQ.
- [x] **2.12 Endpoints.**
  - a. `GET /alertas?estado=` con orden por `dinero_en_riesgo_cop` descendente y cabecera `ETag = version`.
  - b. `GET /alertas/{id}` devolviendo `AlertaVista` completa con nombres resueltos, consultas y propuesta.
  - c. `POST /alertas/{id}/procesar` para ejecutar pipeline hasta generación de propuesta y suspensión HITL.
  - d. `POST /alertas/{id}/decision` con validación de `Idempotency-Key` e `If-Match`, manejando `400` y `409` (`transicion_invalida` y `conflicto_version`), reanudando el grafo y ejecutando borradores sandbox.
  - **Hecho cuando:** probado de punta a punta en `evals/test_fase2_agentes.py::test_api_procesar_y_decision_flujo_completo`.

### 2E. Ejecutor y bitácora `[BAK]`
- [x] **2.13 Ejecutor.** Tres generadores de borradores (`correo`, `tarea`, `orden_compra`) con destino `sandbox://`; solo con estado `aprobada`; idempotente por `accion_id`; `ResultadoEjecucion`. Probado en `evals/test_escenarios_e2e.py` y `scripts/run_smoke_test_s1.py`.
- [x] **2.14 Bitácora inmutable.**
  - a. `EntradaBitacora.sellar` en cada evento (creación, análisis, propuesta, decisión, ejecución, guardrail, error).
  - b. `PutItem` condicional `attribute_not_exists(seq)`.
  - c. IAM de la Lambda con Deny de `dynamodb:UpdateItem` y `DeleteItem` sobre `centinela_bitacora`.
  - d. `GET /bitacora?alerta_id=&verificar=true` y `GET /bitacora/{id}?verificar=true` ejecutan `verificar_cadena`.
  - e. Evaluado en `evals/test_bitacora_seguridad.py`: manipulación de payload, hash o secuencia rompe la cadena y es detectada. Flujo completo con 5+ entradas encadenadas y verificadas.
  - **Hecho cuando:** el flujo completo deja 4+ entradas encadenadas y verificadas al 100%.
- [x] **2.15 Aprobar, editar, rechazar.** Rechazar exige motivo (≥ 10 caracteres), guarda el motivo en la bitácora y en `config/feedback` (base del aprendizaje por rechazo). Editar valida los parámetros con la unión discriminada y los aplica a los borradores sandbox.
  - **Hecho cuando:** las tres decisiones tienen test de punta a punta pasando en `evals/test_escenarios_e2e.py` (S1 aprobar, S2 editar, S4 rechazar).

### 2F. Seguridad (EJ-03) `[INF]` + `[BAK]`
- [x] **2.16 Política envenenada / Seguridad (EJ-03).**
  - a. Bedrock Guardrail (`zuonkeflxh8f`) con filtro `PROMPT_ATTACK` con fuerza `HIGH` y capa de defensa en profundidad local.
  - b. Detección y neutralización en `buscar_politica`, chat y analista; marcas `guardrail_ataque_detectado` y `guardrail_intervino` registradas en la bitácora inmutable.
  - c. Evaluado en `evals/test_guardrail.py`, `evals/test_buscar_politica.py`, `evals/test_chat_soporte.py` y consola interactiva `scripts/test_interactive_pipeline.py`.
  - **Hecho cuando:** el agente reporta la instrucción como anomalía y no altera ninguna propuesta.

### 2G. Chat `[BAK]`
- [x] **2.17 `POST /chat` con SSE.** Servicio `backend/services/chat.py` y endpoint `POST /chat` con streaming `ChatEvento` (`token`, `cifra`, `fin`, `error`); contexto anclado a la alerta si se envía `alerta_id`; guardrail de entrada y salida; consultas de solo lectura a la capa semántica y políticas. Evaluado en `evals/test_chat_soporte.py`.
  - **Hecho cuando:** "¿qué otros SKU compra este proveedor?" responde con cifras y fuente, y cierra con `fin` (consultas y costo).
- [x] **2.18 "No tengo evidencia suficiente."** El chat y el Analista usan esta respuesta formal cuando las consultas no respaldan la respuesta. Probado en `evals/test_chat_soporte.py::test_chat_sin_evidencia_suficiente`.

- **GATE día 2 mediodía:** flujo completo por `curl` hasta `ejecutada` en la nube, bitácora verificada. Superado con éxito (83 de 83 tests pasando).

---

## Fase 3 · Frontend en Amplify (Día 2 mañana-tarde) `[FRO]`
- [x] **3.1 Proyecto.** Creado en `frontend/` con Vite + React 18 + TypeScript + Tailwind CSS v3 con paleta minimalista off-white (`#f8fafc`), superficies blancas `#ffffff`, Lucide React, Recharts y Sonner. Compilación limpia y ligera (dist 283 KB js / 31 KB css).
- [x] **3.2 Cliente tipado.** `frontend/src/api/client.ts` con tipos TypeScript sincronizados con los contratos de FastAPI (`AlertaVista`, `DiagnosticoLLM`, `DecisionRequest`, `ResultadoEjecucion`, `BitacoraResponse`, `SimulacionCorte`). Manejo de cabeceras `x-api-key`, `x-request-id`, `Idempotency-Key`, `If-Match`, lector de streams SSE para `/chat` y fallback a la Function URL de AWS Lambda.
- [x] **3.3 Bandeja de decisiones (Vista Ejecutiva & Reducción de Ruido).** `frontend/src/components/BandejaDecisiones.tsx` con "Valor en 30 segundos" adaptativo:
  - **Vista Ejecutiva Prioritaria por Defecto ("Decisiones Estratégicas"):** Filtra por defecto la vista principal para mostrar únicamente las alertas de alto impacto de los escenarios del reto (S1 a S6). En el corte inicial limpio (`2026-06-18`), muestra un estado tranquilizador *"Operación en Estado Óptimo · 0 Riesgos Críticos Pendientes"*. En el hito `2026-08-15`, destaca de inmediato la alerta S1 ($23.5M COP en riesgo). En el cierre `2026-09-30`, expone los 5 a 7 casos estratégicos sin sobrecarga.
  - **Pestaña Secundaria "Auditoría Operativa Completa":** Agrupa los 119+ registros históricos de moras menores o rutinarias para que no ensucien la bandeja gerencial.
  - **Flujo de Diagnóstico IA Inteligente:** Botón superior *"Analizar Corte con IA"* para procesar las alertas estratégicas pendientes en lote. Eliminación del texto confuso técnico y reemplazo por el estado claro de negocio *"Pendiente de Diagnóstico IA"* con botón de 1 clic *"Diagnosticar con IA"* y botones HITL inmediatos (*Aprobar*, *Editar*, *Rechazar*).
- [x] **3.4 Reloj simulado y Selector de Calendario en UI.** `frontend/src/components/Topbar.tsx` con selector interactivo:
  - Input date de calendario minimalista restringido estrictamente entre `2026-06-18` y `2026-09-30`.
  - 3 Botones de acceso rápido a los hitos clave de la demo: 🟢 `18 Jun 2026` (Corte Limpio), 🟠 `15 Ago 2026` (Hito S1 $23.5M COP), y 🔴 `30 Sep 2026` (Cierre S1-S5).
  - Navegación temporal bidireccional limpia: si el usuario elige una fecha o hito anterior, reinicia el reloj determinista y avanza automáticamente los días exactos para posicionar la simulación en la fecha elegida. Pasos sutiles `+1 día` y `+7 días`.
- [x] **3.5 Detalle en 3 niveles.** `frontend/src/components/DetalleAlertaModal.tsx` estructurado formalmente en:
  - **Nivel 1:** Resumen ejecutivo de una frase y propuesta del Estratega con impacto en COP.
  - **Nivel 2:** Causa raíz investigada por el Analista, cifras trazables de DuckDB con `consulta_id` y citas formales de políticas PDF (`FIN-POL-004`, `COM-POL-002`, `OPE-POL-007`) con hash SHA-256.
  - **Nivel 3 ("Cómo llegué aquí"):** Sección colapsable que renderiza el SQL exacto ejecutado sobre DuckDB y el hash SHA-256 verificado.
- [x] **3.6 Acciones (HITL).** `frontend/src/components/DecisionModal.tsx` para Aprobar (1-clic con cabecera `Idempotency-Key` y previsualización de artefactos sandbox `sandbox://correos/...`, `sandbox://tareas/...`), Editar (formulario contextual según tipo de acción: slider de % ajuste de precio, nivel de gestión de cobro, vía de OC) y Rechazar (motivo obligatorio $\ge$ 10 caracteres para el aprendizaje por rechazo). Control de concurrencia optimista con manejo de error 409.
- [x] **3.7 Chat anclado.** `frontend/src/components/ChatSoporte.tsx` con streaming Server-Sent Events (SSE) token a token, renderizado de cifras citadas interactivas como etiquetas, costo en USD (Haiku 4.5), consultas ejecutadas y preguntas sugeridas de un solo clic.
- [x] **3.8 Bitácora.** `frontend/src/components/BitacoraViewer.tsx` con tabla de auditoría (secuencia `seq`, actor, evento, fecha/hora, hash SHA-256 copiable y payload JSON expandible). Botón *"Verificar Cadena"* que consulta `GET /bitacora/{id}?verificar=true` y muestra el sello verde *"Cadena criptográfica íntegra y verificada"*.
- [x] **3.9 Configuración.** `frontend/src/components/ConfiguracionPanel.tsx` con control de umbrales para los 5 detectores (margen mínimo, mora máxima, cobertura de inventario, descuentos fuera de política) y matriz de niveles de autonomía (Informa / Propone / Ejecuta; con modo Propone HITL predeterminado).
- [x] **3.10 Panel de costo.** `frontend/src/components/CostoRoiPanel.tsx` con observabilidad financiera, desglose de modelos (Claude Haiku 4.5, Titan v2, DuckDB in-memory), consumo de tokens, costo en USD y multiplicador ROI frente al dinero en riesgo detectado.
- [x] **3.11 Accesibilidad, UI/UX minimalista y responsive.**
  - **Active Persona Switcher** ubicado en el pill inferior del sidebar para alternar con 1 clic entre roles reales: Carlos Mendoza (Gerente Comercial), Ana Restrepo (Directora de Cartera), David Osorio (Líder de Abastecimiento) y Sergio Céspedes (Auditor & Gerencia General), sellando cada decisión con `decidido_por: usuario.id`.
  - Diseño minimalista off-white (`#f8fafc`), tarjetas `rounded-3xl` blancas con bordes suaves `border-slate-200/70`, contrastes limpios (Slate 900 y Slate 500) y acentos pasteles funcionales (menta, ámbar, rosa, celeste).
- [x] **3.12 Despliegue en Amplify.**
  - a. `infra/amplify.tf`: Recurso `aws_amplify_app` con `custom_rule` SPA rewrite a `/index.html`, variables de entorno `VITE_API_URL` y branch `main`. Sintaxis validada con `terraform validate`.
  - b. `scripts/deploy_frontend.py`: Automatización completa con `boto3` para compilar (`npm run build`), empaquetar `dist.zip`, crear despliegue en Amplify, subir vía PUT y activar el release.
  - c. Desplegado y verificado exitosamente en vivo: **`https://main.d1y5ytuqvgx3m2.amplifyapp.com`** (Job ID 1 - `SUCCEED`, HTTP 200 OK vía CloudFront).
- **GATE día 2 tarde:** Demo completa y operativa en el navegador en la nube: reloj interactivo → detección y filtrado de alertas → detalle en 3 niveles → chat SSE → aprobación con Idempotency-Key → verificación criptográfica de bitácora SHA-256. Superado con éxito.

---

## Fase 3b · Monitorización (Día 2 tarde) `[INF]`
Diseño en [05_monitorizacion](docs/02_arquitectura.md).
- [x] **3b.1 Logger JSON.** Servicio `backend/services/telemetry.py` con campos `ts, nivel, request_id, run_id, alerta_id, agente, evento`; middleware FastAPI que propaga y ancla `x-request-id`; sanitización rigurosa de PII y cifras en los logs.
- [x] **3b.2 Métricas EMF** (namespace `Centinela`): Formato canónico AWS EMF implementado en `backend/services/telemetry.py`. Emisión asíncrona de `AlertasGeneradas`, `PipelineLatenciaMs`, `LlmTokensEntrada/Salida`, `CostoUsdPorAlerta`, `ValidacionFallida`, `ReintentosLlm`, `SinEvidencia`, `GuardrailIntervino`, `BitacoraCadenaRota`, `AprobacionesHumanas`, `Rechazos`. Evaluado en `evals/test_telemetry_emf.py` (11/11 tests pasando).
- [x] **3b.3 Logging de Bedrock y trazas.** Trazas de inferencia con tokens, latencia ms y costo USD persistidas en DynamoDB `centinela_trazas` con TTL 30 días (`guardar_traza`) e integradas con la visualización UI "Cómo llegué aquí".
- [x] **3b.4 Dashboard `Centinela-Operaciones`.** Creado en `infra/monitoring.tf` y desplegado con Terraform en AWS CloudWatch. Widgets para: alertas por severidad, latencias p50/p95 por agente, consumo de tokens y costo USD, intervenciones del guardrail, integridad de la cadena de bitácora SHA-256, decisiones HITL y métricas nativas de Lambda.
- [x] **3b.5 Alarmas con SNS (correo).** Creadas en `infra/monitoring.tf` y desplegadas con Terraform: Tópico SNS `centinela-alarmas-operaciones`, suscripción de correo (`serces19@gmail.com`), alarmas para Cadena de bitácora rota (crítica), Latencia p95 > 20s, Prompt injection en guardrail y errores no controlados en Lambda.
- [x] **3b.6 promptfoo.** Manifiesto `evals/promptfoo.yaml` configurado con Bedrock Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`), casos oficiales de EJ-03 (inyecciones de prompt, políticas envenenadas, extracción de prompt de sistema) y regresión de consultas normativas (FIN-POL-004 y OPE-POL-007).
- [x] **3b.7 CI (GitHub Actions).** Pipeline de CI implementado en `.github/workflows/ci.yml` con validación de código (`pytest` con los 94 tests), validación de infraestructura (`terraform validate`) y disparador manual para evaluación de seguridad con promptfoo.
  - **Hecho cuando:** el dashboard de CloudWatch y las alarmas están activos en AWS `us-east-1`, la imagen con telemetría está desplegada en la Lambda y los 94 tests pasan al 100%.

---

## Fase 4 · Despliegue limpio, evaluación y demo (Día 3)

### 4A. Robustez `[INF]`
- [ ] **4.1 Rendimiento.** Alias de Lambda con **provisioned concurrency = 1** durante la demo y Function URL asociada a ese alias; calentamiento previo; medir arranque en frío y latencia p95 de las consultas (objetivo: < 200 ms con la Lambda caliente).
- [ ] **4.2 Topes de costo.** Límite de tokens por alerta y por turno de chat; tope de llamadas por herramienta; alarma de presupuesto activa.
- [ ] **4.3 Secretos.** `x-api-key` en SSM Parameter Store (SecureString), nunca en el repositorio; rotación documentada.
- [x] **4.4 `terraform apply` desde cero (Deploy All).** Script maestro [`scripts/deploy_all.py`](scripts/deploy_all.py) que orquesta de forma secuencial y desatendida: Terraform infra → Sync S3 Políticas & Titan V2 Embeddings → Publicación Guardrail → Build & Push Docker ECR → Update Lambda → Build & Deploy Amplify Hosting → Healthcheck E2E verificado.
  - **Hecho cuando:** un compañero lo ejecuta sin ayuda y la demo funciona.

### 4B. Evaluación `[INF]` + `[DAT]`
- [x] **4.5 Generalización multi-semilla.**
  - a. `SEMILLA=12` y `SEMILLA=42` con `Kit_Equipos/generador/generar_dataset.py`, guardando ground truth en `escenarios.json`.
  - b. Carga de cada dataset en DuckDB en memoria con las 7 vistas semánticas de `views.sql`.
  - c. Verificado en [`evals/test_multi_semilla.py`](evals/test_multi_semilla.py): S1-S5 detectados al 100% con las entidades dinámicas de cada semilla, demostrando cero hardcoding.
  - **Hecho cuando:** S1-S5 pasan en ambas semillas (2/2 tests PASSED).
- [x] **4.6 Evaluación del jurado.** Ejecutada la matriz oficial en [`scripts/ejecutar_evaluacion_jurado.py`](scripts/ejecutar_evaluacion_jurado.py) (EJ-01 preguntas SQL con 0% de error, EJ-02 alertas por fecha con reloj simulado, EJ-03 seguridad y anonimización PII). Informes exportados en [`Kit_Equipos/evaluaciones/informe_casos_prueba_ejecutados.csv`](Kit_Equipos/evaluaciones/informe_casos_prueba_ejecutados.csv) y [`docs/informes/evaluacion_jurado.md`](docs/informes/evaluacion_jurado.md) con **11/11 casos aprobados (100%)**.
- [ ] **4.7 Plan B de demo.** Video grabado de la demo completa y entorno local (`uvicorn` + DuckDB + UI) que funcione sin Bedrock con respuestas pregrabadas **solo como respaldo etiquetado**, nunca presentado como en vivo.

### 4C. Demo y pitch `[NEG]` + todos
- [x] **4.8 Guion de la demo (5 min).** Estructurado al segundo en [`docs/04_evaluacion_y_demo.md`](docs/04_evaluacion_y_demo.md): inicio en corte limpio 2026-06-18 → avance temporal a 2026-08-15 (alerta S1 $23.5M) → detalle en 3 niveles y citas OPE-POL-007 → chat anclado con streaming SSE → aprobación HITL con Active Persona Switcher y bitácora SHA-256 → corte final 2026-09-30 con 5 escenarios → neutralización de ataque EJ-03 → dashboard CloudWatch y ROI 10.000:1.
- [x] **4.9 Pitch de negocio (3 min).** Estructurado en [`docs/04_evaluacion_y_demo.md`](docs/04_evaluacion_y_demo.md): dolor silencioso en distribución masiva, propuesta de valor Centinela, regla de oro determinista, auditoría criptográfica Ley 1581, observabilidad serverless a costo cero en reposo, hoja de ruta de ERPs y matriz de preguntas difíciles del jurado.
- [ ] **4.10 Ensayos.** Mínimo tres ensayos completos cronometrados con el equipo; lista de preguntas difíciles del jurado y respuestas (costos, seguridad, qué pasa si el modelo se equivoca, privacidad Ley 1581).
- [ ] **4.11 Lista de verificación 30 minutos antes.** Reloj reiniciado, provisioned concurrency activa, Bedrock respondiendo, KB sincronizada, `x-api-key` correcta, dashboard abierto, plan B listo.

---

## Opcionales (solo si sobra tiempo; al final)
- [x] **O.1 Backtest con reloj simulado.**
  - a. Script maestro [`scripts/backtest_simulado.py`](scripts/backtest_simulado.py) que avanzó el corte día a día a lo largo del año operativo completo (365 días: 2025-10-01 al 2026-09-30) en 44.8 segundos sobre DuckDB in-memory.
  - b. Días de anticipación calculados: S1 (+16 días), S2 (+351 días), S3 (+1 día), S4 (+89 días), S5 (+352 días), S6 (+26 días).
  - c. Informe oficial generado en [`docs/informes/backtest.md`](docs/informes/backtest.md) con tabla para el pitch y defensa del ROI.
  - **Hecho cuando:** tabla de escenarios con fechas reproducibles completada al 100%.
- [x] **O.2 Explorador de cola larga.**
  - a. Script [`scripts/explorador_cola_larga.py`](scripts/explorador_cola_larga.py) con barrido analítico multidimensional sobre líneas de producto, canales de venta y vendedores.
  - b. Detección estadística robusta (MAD Z-Score) de márgenes atípicos y ventas bajo costo unitario.
  - c. Hipótesis formal del escenario oculto (S6) confirmada con cifras deterministas: SKU `P0097` (Leche en polvo x1) vendido sistemáticamente a un 15.7% bajo costo unitario por V06, V07, V15 y V11, acumulando pérdidas directas de margen.
  - d. Informe exportado en [`docs/informes/cola_larga_s6.md`](docs/informes/cola_larga_s6.md).
  - **Hecho cuando:** hipótesis del escenario oculto sustentada con evidencia de datos reales sin alucinación. Verificado al 100%.
