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
from contracts.base import EstadoAlerta
from contracts.bitacora import EntradaBitacora, verificar_cadena
from contracts.configuracion import CORTE_INICIAL_LIMPIO, FECHA_CORTE_DEFECTO
from contracts.decision import DecisionRequest, ResultadoEjecucion
from contracts.operacion import ChatRequest, ChatToken, ErrorAPI, SimulacionResp
from agents.graph import aplicar_decision_humana, procesar_alerta_completa
from agents.vigia import generar_alertas
from services.chat import generar_respuesta_chat_stream
from services.persistencia import persistencia_service
from services.resolucion import resolver_nombres
from services.telemetry import (
    ctx_request_id,
    emitir_bitacora_cadena_rota,
    emitir_decision_humana,
    log_evento,
)

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
    ctx_request_id.set(request_id)
    start_time = time.perf_counter()

    response: Response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["x-request-id"] = request_id

    log_evento(
        nivel="INFO",
        evento="http.request_completado",
        agente="api",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client=request.client.host if request.client else "unknown",
    )
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
# -----------------------------------------------------------------------------
# Endpoints de Alertas (Vigía, Analista, Estratega y HITL)
# -----------------------------------------------------------------------------
@app.get("/alertas", response_model=list[AlertaVista], tags=["Alertas"])
def listar_alertas(
    response: Response,
    estado: str | None = Query(None, description="Filtrar por estado (p. ej. 'nueva', 'en_analisis', 'propuesta')"),
    corte: date | None = Query(None, description="Fecha de corte para evaluar hallazgos"),
    persistir: bool = Query(False, description="Persistir hallazgos en DynamoDB y bitacora"),
):
    """Devuelve las alertas enriquecidas con nombres resueltos y propuestas si existen (AlertaVista)."""
    fecha_eval = corte or persistencia_service.obtener_reloj()["corte"]

    # Consultar alertas persistidas
    persisted = persistencia_service.listar_alertas(estado=estado)
    persisted_al_corte = [a for a in persisted if a.corte_creacion <= fecha_eval]
    if persisted_al_corte:
        alertas = persisted_al_corte
    else:
        # Generación determinista del Vigía para la fecha de corte
        alertas = generar_alertas(fecha_eval)
        if persistir and alertas:
            persistencia_service.persistir_alertas_vigia(alertas)
        if estado:
            alertas = [a for a in alertas if (a.estado.value if hasattr(a.estado, "value") else str(a.estado)) == estado]

    # Recolectar todas las entidades para resolución determinista de nombres
    todas_entidades: set[str] = set()
    for a in alertas:
        for h in a.hallazgos:
            for ent in h.entidades:
                todas_entidades.add(ent.id)

    nombres_map = resolver_nombres(todas_entidades)

    vistas: list[AlertaVista] = []
    for a in alertas:
        nombres_alerta = {ent.id: nombres_map[ent.id] for h in a.hallazgos for ent in h.entidades if ent.id in nombres_map}
        propuesta = persistencia_service.obtener_propuesta(a.alerta_id)
        vista = AlertaVista(
            alerta=a,
            nombres_resueltos=nombres_alerta,
            propuesta=propuesta,
            consultas=[],
        )
        vistas.append(vista)

    return vistas


@app.get("/alertas/{alerta_id}", response_model=AlertaVista, tags=["Alertas"])
def obtener_alerta_detalle(alerta_id: str, request: Request, response: Response):
    """Consulta el detalle enriquecido de una alerta con propuesta, nombres y consultas (AlertaVista)."""
    request_id = getattr(request.state, "request_id", "req-unknown")
    alerta = persistencia_service.obtener_alerta(alerta_id)

    if not alerta:
        fecha_eval = persistencia_service.obtener_reloj()["corte"]
        alertas = generar_alertas(fecha_eval)
        for a in alertas:
            if a.alerta_id == alerta_id:
                alerta = a
                break

    if not alerta:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorAPI(
                codigo="no_encontrado",
                mensaje=f"Alerta '{alerta_id}' no encontrada.",
                request_id=request_id,
            ).model_dump(mode="json"),
        )

    # Entidades y nombres
    entidades = {ent.id for h in alerta.hallazgos for ent in h.entidades}
    nombres_resueltos = resolver_nombres(entidades)

    propuesta = persistencia_service.obtener_propuesta(alerta.alerta_id)
    trazas = persistencia_service.obtener_trazas(alerta.alerta_id)
    consultas_ids = list({cid for t in trazas for cid in t.consulta_ids})

    response.headers["ETag"] = f'"{alerta.version}"'

    return AlertaVista(
        alerta=alerta,
        nombres_resueltos=nombres_resueltos,
        propuesta=propuesta,
        consultas=consultas_ids,
    )


@app.post("/alertas/{alerta_id}/procesar", tags=["Alertas"])
async def procesar_alerta_endpoint(
    alerta_id: str,
    request: Request,
    response: Response,
    corte: date | None = Query(None, description="Fecha de corte para el análisis"),
):
    """Dispara el pipeline de agentes para una alerta: nueva -> en_analisis -> propuesta."""
    request_id = getattr(request.state, "request_id", "req-unknown")
    alerta = persistencia_service.obtener_alerta(alerta_id)

    if not alerta:
        fecha_eval = corte or persistencia_service.obtener_reloj()["corte"]
        alertas = generar_alertas(fecha_eval)
        persistencia_service.persistir_alertas_vigia(alertas)
        alerta = persistencia_service.obtener_alerta(alerta_id)

    if not alerta:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorAPI(
                codigo="no_encontrado",
                mensaje=f"Alerta '{alerta_id}' no encontrada.",
                request_id=request_id,
            ).model_dump(mode="json"),
        )

    fecha_corte = corte or alerta.corte_creacion
    alerta_act, propuesta = await procesar_alerta_completa(alerta_id, corte=fecha_corte)

    entidades = {ent.id for h in alerta_act.hallazgos for ent in h.entidades}
    nombres_map = resolver_nombres(entidades)

    response.headers["ETag"] = f'"{alerta_act.version}"'

    return AlertaVista(
        alerta=alerta_act,
        nombres_resueltos=nombres_map,
        propuesta=propuesta,
        consultas=[],
    )


@app.post("/alertas/{alerta_id}/decision", tags=["Alertas"])
def tomar_decision_endpoint(
    alerta_id: str,
    decision: DecisionRequest,
    request: Request,
    response: Response,
):
    """Aplica la decisión humana (aprobar, editar, rechazar) con control de concurrencia e idempotencia.

    Requiere cabecera obligatoria 'Idempotency-Key' y soporta 'If-Match: <version>'.
    """
    request_id = getattr(request.state, "request_id", "req-unknown")

    # Validar cabecera Idempotency-Key
    idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    if not idempotency_key:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorAPI(
                codigo="validacion",
                mensaje="La cabecera 'Idempotency-Key' es obligatoria para registrar decisiones.",
                request_id=request_id,
            ).model_dump(mode="json"),
        )

    # Validar cabecera If-Match (versión optimista)
    if_match = request.headers.get("If-Match") or request.headers.get("if-match")
    version_previa = None
    if if_match:
        try:
            version_previa = int(if_match.strip('"').strip())
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ErrorAPI(
                    codigo="validacion",
                    mensaje="La cabecera 'If-Match' debe contener un número de versión válido.",
                    request_id=request_id,
                ).model_dump(mode="json"),
            )

    alerta = persistencia_service.obtener_alerta(alerta_id)
    if not alerta:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorAPI(
                codigo="no_encontrado",
                mensaje=f"Alerta '{alerta_id}' no encontrada.",
                request_id=request_id,
            ).model_dump(mode="json"),
        )

    # Idempotencia: si la alerta ya fue ejecutada o rechazada, retornar resultado previo sin error
    if alerta.estado in (EstadoAlerta.APROBADA, EstadoAlerta.EJECUTADA, EstadoAlerta.RECHAZADA):
        res_prev = persistencia_service.obtener_resultado_ejecucion(alerta_id)
        if res_prev:
            return {"alerta": alerta.model_dump(mode="json"), "resultado": res_prev.model_dump(mode="json")}

    # Conflicto de versión optimista
    if version_previa is not None and alerta.version != version_previa:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ErrorAPI(
                codigo="conflicto_version",
                mensaje=f"Conflicto de versión optimista: versión actual es {alerta.version}, esperada {version_previa}.",
                request_id=request_id,
                detalle={"version_actual": alerta.version, "version_esperada": version_previa},
            ).model_dump(mode="json"),
        )

    # Transición de estado inválida
    if alerta.estado != EstadoAlerta.PROPUESTA:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ErrorAPI(
                codigo="transicion_invalida",
                mensaje=f"Transición inválida desde estado '{alerta.estado.value}'. Solo se permiten decisiones en estado 'propuesta'.",
                request_id=request_id,
                detalle={"estado_actual": alerta.estado.value},
            ).model_dump(mode="json"),
        )

    # Aplicar decisión humana
    try:
        alerta_final, resultado = aplicar_decision_humana(
            alerta_id=alerta_id,
            decision=decision,
            version_previa=version_previa,
        )
        dec_str = str(decision.decision)
        emitir_decision_humana(dec_str)
        log_evento(
            nivel="INFO",
            evento="hitl.decision_aplicada",
            agente="hitl",
            alerta_id=alerta_id,
            decision=dec_str,
            actor=decision.decidido_por,
        )
        response.headers["ETag"] = f'"{alerta_final.version}"'
        return {
            "alerta": alerta_final.model_dump(mode="json"),
            "resultado": resultado.model_dump(mode="json"),
        }
    except Exception as e:
        logger.error(f"Error aplicando decision para {alerta_id}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorAPI(
                codigo="interno",
                mensaje=f"Error al ejecutar decisión humana: {e}",
                request_id=request_id,
            ).model_dump(mode="json"),
        )


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
    if verificar and entradas:
        cadena_valida = verificar_cadena(entradas)
        if not cadena_valida:
            emitir_bitacora_cadena_rota(tipo="sha256_o_secuencia_invalida")
            log_evento(
                nivel="CRITICAL",
                evento="bitacora.cadena_rota",
                agente="bitacora",
                alerta_id=alerta_id,
                tipo="sha256_o_secuencia_invalida",
            )
    else:
        cadena_valida = True

    return {
        "alerta_id": alerta_id,
        "total_entradas": len(entradas),
        "cadena_valida": cadena_valida,
        "entradas": [e.model_dump(mode="json") for e in entradas],
    }


@app.get("/bitacora", tags=["Bitacora"])
def consultar_bitacora_query(
    alerta_id: str = Query(..., description="ID de la alerta a consultar"),
    verificar: bool = Query(False, description="Ejecutar verificacion criptografica de hash SHA-256"),
):
    """Consulta la cadena inmutable de bitácora mediante query parameter (Handshake H10)."""
    return consultar_bitacora(alerta_id=alerta_id, verificar=verificar)


# -----------------------------------------------------------------------------
# Endpoints de Chat de Soporte (Handshake H9 / Tarea 2.17)
# -----------------------------------------------------------------------------
@app.post("/chat", tags=["Chat"])
async def chat_endpoint(request: ChatRequest):
    """Chat interactivo de soporte anclado a alerta o libre con streaming Server-Sent Events (SSE)."""
    return StreamingResponse(
        generar_respuesta_chat_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

