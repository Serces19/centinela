# backend/api/main.py
"""API FastAPI de Centinela.

Endpoints principales:
- GET /health: Healthcheck del servicio.
- GET /stream: Streaming SSE para verificación de Lambda Web Adapter.
- POST /simulacion/avanzar: Avanzar el reloj de simulación temporal.
- GET /simulacion/corte: Consultar fecha de corte actual y fecha inicial limpia.
- POST /simulacion/reiniciar: Restablecer el reloj al corte inicial limpio.
- GET /alertas: Listar alertas del Vigía enriquecidas con nombres resueltos (AlertaVista).
- GET /bitacora: Consultar y verificar la cadena inmutable de bitácora para una alerta.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
import json
import logging
import time
from typing import Any
import uuid

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from contracts.alertas import AlertaVista
from contracts.bitacora import EntradaBitacora, verificar_cadena
from contracts.configuracion import CORTE_INICIAL_LIMPIO, FECHA_CORTE_DEFECTO
from contracts.operacion import ChatToken, ErrorAPI, SimulacionResp
from agents.vigia import generar_alertas
from services.persistencia import persistencia_service
from services.resolucion import resolver_nombres

# Configuración de Logging JSON estructurado
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("centinela.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup", "msg": "Iniciando Centinela API"}))
    yield
    logger.info(json.dumps({"event": "shutdown", "msg": "Apagando Centinela API"}))


app = FastAPI(
    title="Centinela API",
    version="0.1.0",
    description="Sistema serverless de agentes de IA de vigilancia operacional y financiera",
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# Middleware de CORS
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Middleware de Logging JSON Estructurado y Propagación de x-request-id
# -----------------------------------------------------------------------------
@app.middleware("http")
async def logging_and_request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    start_time = time.perf_counter()

    response: Response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["x-request-id"] = request_id

    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "client": request.client.host if request.client else "unknown",
    }
    logger.info(json.dumps(log_entry))
    return response


# -----------------------------------------------------------------------------
# Endpoints de Salud y Diagnóstico
# -----------------------------------------------------------------------------
@app.get("/health", tags=["Salud"])
def health():
    """Healthcheck estándar para balanceadores, ALB y monitores."""
    return {"status": "ok", "version": "0.1.0", "servicio": "centinela"}


# -----------------------------------------------------------------------------
# Endpoint SSE para Streaming (Lambda Web Adapter)
# -----------------------------------------------------------------------------
@app.get("/stream", tags=["Streaming"])
async def stream():
    """Emite 5 eventos en streaming vía Server-Sent Events (SSE).

    Usado para verificar que el AWS Lambda Web Adapter opera en modo `response_stream`
    sin buffering intermedio.
    """

    async def event_generator():
        for i in range(1, 6):
            payload = ChatToken(
                evento="token",
                texto=f"Evento SSE {i}/5 - Transmisión en tiempo real Centinela",
            )
            yield f"data: {payload.model_dump_json()}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# -----------------------------------------------------------------------------
# Endpoints de Simulación Temporal (Reloj)
# -----------------------------------------------------------------------------
@app.get("/simulacion/corte", tags=["Simulacion"])
def obtener_corte():
    """Consulta la fecha de corte actual del reloj y los límites permitidos."""
    estado_reloj = persistencia_service.obtener_reloj()
    return {
        "corte": estado_reloj["corte"],
        "corte_inicial_limpio": CORTE_INICIAL_LIMPIO,
        "corte_maximo": FECHA_CORTE_DEFECTO,
        "run_id": estado_reloj["run_id"],
        "actualizado_en": estado_reloj["actualizado_en"],
    }


@app.post("/simulacion/avanzar", response_model=SimulacionResp, tags=["Simulacion"])
def avanzar_simulacion(
    request: Request,
    dias: int = Query(None, ge=1, le=365, description="Número de días a avanzar"),
    body: dict[str, Any] | None = Body(None),
):
    """Avanza la fecha de corte del simulador temporal.

    - Acepta `dias` vía Query parameter o JSON body.
    - Valida que no supere `2026-09-30`.
    - Actualiza el estado en `centinela_reloj`.
    - Responde con `SimulacionResp` (Handshake H1).
    """
    num_dias = dias
    if num_dias is None and body and "dias" in body:
        try:
            num_dias = int(body["dias"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El campo 'dias' en el cuerpo debe ser un entero.",
            )

    if num_dias is None or num_dias < 1 or num_dias > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe especificar 'dias' entre 1 y 365.",
        )

    estado_actual = persistencia_service.obtener_reloj()
    corte_actual: date = estado_actual["corte"]
    nuevo_corte = corte_actual + timedelta(days=num_dias)

    if nuevo_corte > FECHA_CORTE_DEFECTO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El corte simulado ({nuevo_corte}) supera la fecha maxima permitida ({FECHA_CORTE_DEFECTO}).",
        )

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    persistencia_service.actualizar_reloj(nuevo_corte, run_id)

    return SimulacionResp(
        run_id=run_id,
        corte=nuevo_corte,
        dias_avanzados=num_dias,
        pipeline_disparado=True,
    )


@app.post("/simulacion/reiniciar", response_model=SimulacionResp, tags=["Simulacion"])
def reiniciar_simulacion():
    """Restablece el reloj de simulación al corte inicial limpio (2026-06-18)."""
    estado = persistencia_service.reiniciar_reloj()
    return SimulacionResp(
        run_id=estado["run_id"],
        corte=estado["corte"],
        dias_avanzados=0,
        pipeline_disparado=False,
    )


# -----------------------------------------------------------------------------
# Endpoints de Alertas (Vigía y Persistencia)
# -----------------------------------------------------------------------------
@app.get("/alertas", response_model=list[AlertaVista], tags=["Alertas"])
def listar_alertas(
    estado: str | None = Query(None, description="Filtrar por estado (p. ej. 'nueva', 'en_analisis')"),
    corte: date | None = Query(None, description="Fecha de corte para evaluar hallazgos"),
    persistir: bool = Query(False, description="Persistir hallazgos en DynamoDB y bitacora"),
):
    """Genera y devuelve las alertas del Vigía enriquecidas con nombres resueltos (AlertaVista).

    Si no se especifica `corte`, usa la fecha de corte actual del reloj de simulación.
    """
    fecha_eval = corte
    if fecha_eval is None:
        fecha_eval = persistencia_service.obtener_reloj()["corte"]

    # Generación determinista del Vigía
    alertas = generar_alertas(fecha_eval)

    # Persistencia opcional o automática
    if persistir and alertas:
        persistencia_service.persistir_alertas_vigia(alertas)

    # Filtrar por estado si se solicitó
    if estado:
        alertas = [a for a in alertas if a.estado.value == estado]

    # Recolectar todas las entidades para resolución determinista de nombres
    todas_entidades: set[str] = set()
    for a in alertas:
        for h in a.hallazgos:
            for ent in h.entidades:
                todas_entidades.add(ent.id)

    nombres_map = resolver_nombres(todas_entidades)

    # Construir AlertaVista con nombres enriquecidos
    vistas: list[AlertaVista] = []
    for a in alertas:
        # Nombres relevantes para esta alerta
        nombres_alerta: dict[str, str] = {}
        for h in a.hallazgos:
            for ent in h.entidades:
                if ent.id in nombres_map:
                    nombres_alerta[ent.id] = nombres_map[ent.id]

        vista = AlertaVista(
            alerta=a,
            nombres_resueltos=nombres_alerta,
            propuesta=None,
            consultas=[],
        )
        vistas.append(vista)

    return vistas


# -----------------------------------------------------------------------------
# Endpoints de Bitácora (Handshake H10)
# -----------------------------------------------------------------------------
@app.get("/bitacora/{alerta_id}", tags=["Bitacora"])
def consultar_bitacora(
    alerta_id: str,
    verificar: bool = Query(False, description="Ejecutar verificacion criptografica de hash SHA-256"),
):
    """Consulta la cadena inmutable de bitácora para una alerta dada."""
    entradas = persistencia_service.obtener_bitacora(alerta_id)
    cadena_valida = verificar_cadena(entradas) if (verificar and entradas) else True

    return {
        "alerta_id": alerta_id,
        "total_entradas": len(entradas),
        "cadena_valida": cadena_valida,
        "entradas": [e.model_dump(mode="json") for e in entradas],
    }
