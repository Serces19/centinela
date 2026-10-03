# 04 · Diagramas de arquitectura y flujo de información

Diagramas Mermaid (se renderizan en GitHub, VS Code y la mayoría de visores). Contratos de cada flecha: [03_contratos_datos.md](03_contratos_datos.md).

## 1. Arquitectura completa

```mermaid
flowchart TB
    U([Usuario<br/>gerente / líder de proceso])

    subgraph FE[AWS Amplify Hosting]
        UI[React + Vite<br/>Bandeja · Detalle · Chat · Bitácora · Config]
    end

    subgraph COMP[Cómputo us-east-1]
        FURL[Lambda Function URL<br/>RESPONSE_STREAM · CORS · x-api-key]
        subgraph LAM[Lambda contenedor ECR · FastAPI + Web Adapter]
            API[API rápida<br/>/simulacion · /alertas · /decision · /chat · /bitacora]
            subgraph LG[LangGraph]
                VIG[1 Vigía<br/>reglas + z-score/MAD]
                ANA[2 Analista<br/>Haiku 4.5]
                EST[3 Estratega<br/>Haiku 4.5]
                HITL{{4 interrupt<br/>aprobación humana}}
                EJE[5 Ejecutor<br/>borradores sandbox]
            end
            MCP[Herramientas FastMCP in-process<br/>consultar_vista · buscar_politica<br/>calcular_impacto · crear_borrador]
            DDB_FILE[(centinela.duckdb<br/>solo lectura · 7 vistas · corte)]
        end
        DLQ[[SQS DLQ<br/>invocaciones fallidas]]
    end

    subgraph AI[Amazon Bedrock]
        HK[Claude Haiku 4.5<br/>us.anthropic.claude-haiku-4-5-20251001-v1:0]
        GR[Guardrails<br/>PII ANONYMIZE + PROMPT_ATTACK]
        KB[Knowledge Base<br/>Titan Embeddings V2]
    end

    subgraph STO[Almacenamiento]
        S3P[(S3 · 3 PDFs de políticas)]
        S3V[(S3 Vectors · índice)]
        DDB[(DynamoDB<br/>alertas · bitácora · checkpoints · trazas · reloj)]
    end

    subgraph OBS[Observabilidad AWS]
        CW[CloudWatch<br/>logs JSON · métricas EMF · dashboard · alarmas]
        XR[X-Ray]
        BIL[Bedrock invocation logging]
        BUD[AWS Budgets]
    end

    U --> UI
    UI -->|HTTPS · SSE| FURL --> API
    API -->|auto-invocación async| LG
    API <--> DDB
    VIG --> ANA --> EST --> HITL
    HITL -->|Command resume| EJE
    VIG --> MCP
    ANA --> MCP
    EST --> MCP
    EJE --> MCP
    MCP --> DDB_FILE
    ANA -->|Converse tool use| HK
    EST -->|Converse tool use| HK
    API -->|chat| HK
    HK -.-> GR
    MCP -->|Retrieve| KB
    KB --> S3V
    KB --> S3P
    LG <-->|checkpoints| DDB
    EJE -->|sella hash| DDB
    LAM --> CW
    LAM --> XR
    HK --> BIL --> CW
    LAM -.->|errores async| DLQ
    CW --> BUD
```

## 2. Flujo de información ida y vuelta: escenario real S1 (margen de Hogar)

Datos reales: el 2026-08-15 el proveedor `PR08` sube **+25 %** el costo de `P0001`, `P0006`, `P0011` y `P0021` sin cambio en la lista de precios. Impacto calculado con las unidades de los 30 días previos × aumento de costo: **$23.558.346 COP/mes**.

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant UI as Amplify UI
    participant API as Lambda API
    participant PIPE as Lambda LangGraph
    participant DB as DuckDB vistas
    participant KB as Bedrock KB
    participant LLM as Haiku 4.5 + Guardrail
    participant DDB as DynamoDB
    participant CW as CloudWatch

    Note over U,CW: IDA - del reloj a la alerta
    U->>UI: Avanzar reloj hasta 2026-08-15
    UI->>API: POST /simulacion/avanzar (x-request-id)
    API->>DDB: guarda corte 2026-08-15
    API-->>UI: 202 run_id y corte
    API->>PIPE: Invoke Event PipelineEvent vigia
    PIPE->>DB: consultar_vista costos y margen con corte
    DB-->>PIPE: PR08 costo +25 por ciento en 4 SKU
    PIPE->>DDB: Alerta nueva + bitácora alerta_creada (hash 1)
    UI->>API: GET /alertas (polling 2 s)
    API-->>UI: Alerta nueva, en riesgo $23.558.346

    Note over PIPE,LLM: ANALISIS - dos herramientas y un modelo
    PIPE->>DDB: estado en_analisis
    PIPE->>DB: consultar_vista margen semanal Hogar
    DB-->>PIPE: ConsultaRegistrada y filas
    PIPE->>KB: buscar_politica costo sube más de 5 por ciento
    KB-->>PIPE: fragmento OPE-POL-007 sección 4
    PIPE->>LLM: Converse con IDs y fragmento en datos_politica
    LLM-->>PIPE: DiagnosticoLLM validado con Pydantic
    PIPE->>DDB: bitácora analisis_completo (hash 2)

    Note over PIPE,LLM: ESTRATEGA - el modelo propone, Python calcula
    PIPE->>LLM: propón entre una y tres acciones
    LLM-->>PIPE: PropuestaLLM ajuste_precio sin montos
    PIPE->>DB: calcular_impacto unidades 30d x aumento de costo
    DB-->>PIPE: ImpactoCalculado 23.558.346 COP mensual
    PIPE->>DDB: Propuesta + estado propuesta + checkpoint (interrupt)
    Note over PIPE: La Lambda termina. No hay cómputo mientras se espera.

    Note over U,CW: VUELTA - del humano a la acción
    UI->>API: GET /alertas?estado=propuesta
    API-->>UI: Bandeja ordenada por pesos en riesgo
    U->>UI: Abre la alerta
    UI->>API: GET /alertas/ALR-20260815-xxxxxx
    API-->>UI: causa, cifras trazables, política citada, acciones
    U->>UI: Pregunta qué otros SKU compra este proveedor
    UI->>API: POST /chat (SSE)
    API->>DB: consultar_vista por proveedor
    API->>LLM: Converse con streaming
    LLM-->>API: tokens
    API-->>UI: eventos token, cifra y fin con costo
    U->>UI: Aprobar ajuste de precio
    UI->>API: POST /decision (Idempotency-Key, If-Match)
    API->>DDB: estado aprobada + bitácora decision_humana (hash 3)
    API->>PIPE: Invoke Event reanudar
    PIPE->>DDB: lee checkpoint y reanuda el grafo
    PIPE->>DDB: Borrador sandbox + estado ejecutada + bitácora (hash 4)
    UI->>API: GET /alertas/ALR-20260815-xxxxxx y /bitacora
    API-->>UI: ejecutada y cadena de hashes verificada

    PIPE-->>CW: métricas EMF y logs en cada paso
    LLM-->>CW: invocation logging y tokens
```

## 3. Ciclo de vida de una alerta

```mermaid
stateDiagram-v2
    [*] --> nueva: Vigía detecta
    nueva --> en_analisis: Pipeline toma la alerta
    en_analisis --> propuesta: Diagnóstico y acciones válidos
    en_analisis --> sin_evidencia: Modelo reporta evidencia insuficiente
    en_analisis --> fallida: Error o validación fallida dos veces
    propuesta --> aprobada: Humano aprueba o edita
    propuesta --> rechazada: Humano rechaza con motivo
    aprobada --> ejecutada: Ejecutor crea borradores
    aprobada --> fallida: Error del Ejecutor
    fallida --> nueva: Reintento manual
    sin_evidencia --> [*]
    rechazada --> [*]
    ejecutada --> [*]
```

## 4. Linaje de una cifra (de CSV a pantalla)

```mermaid
flowchart LR
    CSV[(15 CSV oficiales)] -->|build_duckdb.py| DDBF[(centinela.duckdb<br/>en la imagen)]
    DDBF --> VW[7 vistas v_*<br/>parámetro corte]
    VW -->|ConsultarVistaIn validado| Q[ConsultaRegistrada<br/>sql + corte + hash]
    Q --> CT[CifraTrazable<br/>valor + unidad + consulta_id]
    Q --> TR[(trazas en DynamoDB)]
    CT --> LLM[LLM redacta texto<br/>sin números sueltos]
    LLM --> V{numeros_sueltos<br/>vacío?}
    V -->|no| RE[1 reintento con error]
    RE --> LLM
    V -->|sí| UI[UI: cifra + enlace<br/>Cómo llegué aquí]
    TR --> UI
```

## 5. Observabilidad y control de costo

```mermaid
flowchart LR
    L[Lambda<br/>logs JSON + EMF] --> CW[CloudWatch<br/>dashboard Centinela-Operaciones]
    B[Bedrock<br/>AWS/Bedrock + invocation logging] --> CW
    X[X-Ray] --> CW
    T[(trazas DynamoDB<br/>costo_usd por alerta)] --> UI[UI: panel de costo]
    CW --> AL{{Alarmas<br/>cadena rota · DLQ · p95 · costo}}
    AL --> SNS[SNS correo]
    BU[AWS Budgets] --> SNS
    P[promptfoo + pytest<br/>CI] --> R[Informe de evaluación]
```
