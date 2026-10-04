# backend/api/main.py
"""API FastAPI de Centinela.

Endpoints (todos exigen `x-api-key`, salvo /health):
- GET  /health                          Estado del servicio.
- GET  /simulacion/corte                Corte actual del reloj simulado.
- POST /simulacion/avanzar?dias=n       Mueve el reloj, ejecuta el Vigía y persiste las alertas nuevas.
- POST /simulacion/reiniciar            Vuelve al corte limpio y borra el estado de la demo.
- GET  /alertas                         Una alerta por causa, ordenadas por dinero en riesgo.
- GET  /alertas/resumen                 Dinero en riesgo y las decisiones clave.
- GET  /alertas/{id}                    Detalle: causa, evidencia, propuesta.
- POST /alertas/{id}/procesar           Analista y Estratega: nueva -> en_analisis -> propuesta.
- POST /alertas/{id}/decision           Aprobar, editar o rechazar (con motivo).
- GET  /consultas/{id}                  Consulta registrada (SQL, corte, filas y hash) para "Cómo llegué aquí".
- GET  /bitacora                        Auditoría de una alerta o general, con verificación de la cadena.
- GET/PUT /config                       Umbrales del Vigía y autonomía por tipo de acción.
- POST /chat                            Preguntas en lenguaje natural (streaming SSE).
"""

from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import json
import logging
import os
import time
from typing import Any
import uuid

from fastapi import Body, FastAPI, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agents.pipeline import aplicar_decision_humana, procesar_alerta_completa, reabrir_alerta
from agents.vigia import generar_alertas
from contracts.alertas import Alerta, AlertaVista, ResumenAlertas
from contracts.base import EstadoAlerta
from contracts.bitacora import verificar_cadena
from contracts.configuracion import (
    CORTE_INICIAL_LIMPIO,
    FECHA_CORTE_DEFECTO,
    ConfigUmbral,
    ConfiguracionUpdate,
    ConfiguracionVigia,
)
from contracts.decision import DecisionRequest
from contracts.operacion import ChatRequest, ErrorAPI, SimulacionResp
from services.auth import RUTAS_PUBLICAS, auth_deshabilitada, clave_valida
from services.chat import generar_respuesta_chat_stream
from services.persistencia import persistencia_service
from services.registro_consultas import consulta_en_cache
from services.resolucion import resolver_nombres
from services.telemetry import (
    ctx_request_id,
    emitir_bitacora_cadena_rota,
    emitir_decision_humana,
    log_evento,
)
from services.umbrales import (
    META_UMBRALES,
    ConfiguracionInvalida,
    Umbrales,
    cargar_autonomia,
    cargar_umbrales,
    guardar_autonomia,
    guardar_umbrales,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("centinela.api")

ESTADOS_PENDIENTES = (EstadoAlerta.NUEVA, EstadoAlerta.EN_ANALISIS, EstadoAlerta.PROPUESTA)
ESTADOS_RESUELTOS = (EstadoAlerta.APROBADA, EstadoAlerta.EJECUTADA, EstadoAlerta.RECHAZADA, EstadoAlerta.SIN_EVIDENCIA)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup", "msg": "Iniciando Centinela API"}))
    yield
    logger.info(json.dumps({"event": "shutdown", "msg": "Apagando Centinela API"}))


app = FastAPI(
    title="Centinela API",
    version="1.0.0",
    description="Sistema serverless de agentes de IA de vigilancia operacional y financiera",
    lifespan=lifespan,
)

# En AWS Lambda la Function URL ya gestiona CORS; activarlo aquí duplicaría la cabecera.
if not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# -----------------------------------------------------------------------------
# Middleware: autenticación (x-api-key), logging JSON y propagación de x-request-id
# -----------------------------------------------------------------------------
@app.middleware("http")
async def logging_and_request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    ctx_request_id.set(request_id)
    start_time = time.perf_counter()

    requiere_clave = (
        request.method != "OPTIONS" and request.url.path not in RUTAS_PUBLICAS and not auth_deshabilitada()
    )
    if requiere_clave and not clave_valida(request.headers.get("x-api-key")):
        response: Response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=ErrorAPI(
                codigo="no_autorizado",
                mensaje="Falta la cabecera x-api-key o es inválida.",
                request_id=request_id,
            ).model_dump(mode="json"),
        )
    else:
        response = await call_next(request)

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


def _error(request: Request, codigo: str, mensaje: str, http: int, detalle: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=http,
        content=ErrorAPI(
            codigo=codigo,
            mensaje=mensaje,
            request_id=getattr(request.state, "request_id", "req-unknown"),
            detalle=detalle,
        ).model_dump(mode="json"),
    )


# -----------------------------------------------------------------------------
# Alertas vivas (Vigía) con caché corta: evita recalcular en cada sondeo de la UI
# -----------------------------------------------------------------------------
_VIVAS_TTL_S = 4.0
_vivas_cache: dict[tuple[date, str], tuple[float, list[Alerta]]] = {}


def _alertas_vivas(corte: date) -> list[Alerta]:
    umbrales = cargar_umbrales()
    clave = (corte, json.dumps(asdict(umbrales), sort_keys=True))
    ahora = time.monotonic()
    hit = _vivas_cache.get(clave)
    if hit and ahora - hit[0] < _VIVAS_TTL_S:
        return hit[1]
    vivas = generar_alertas(corte, umbrales=umbrales)
    _vivas_cache.clear()
    _vivas_cache[clave] = (ahora, vivas)
    return vivas


def _alertas_sincronizadas(corte: date, crear: bool) -> list[Alerta]:
    return persistencia_service.sincronizar_alertas(_alertas_vivas(corte), crear=crear)


def _vistas(alertas: list[Alerta]) -> list[AlertaVista]:
    entidades = {e.id for a in alertas for h in a.hallazgos for e in h.entidades}
    nombres = resolver_nombres(entidades)
    ids_con_propuesta = [a.alerta_id for a in alertas if a.estado not in (EstadoAlerta.NUEVA, EstadoAlerta.EN_ANALISIS)]
    propuestas = persistencia_service.obtener_propuestas(ids_con_propuesta)
    return [
        AlertaVista(
            alerta=a,
            nombres_resueltos={e.id: nombres[e.id] for h in a.hallazgos for e in h.entidades if e.id in nombres},
            propuesta=propuestas.get(a.alerta_id),
            consultas=sorted({cid for h in a.hallazgos for cid in h.consulta_ids}),
        )
        for a in alertas
    ]


def _alerta_actual(alerta_id: str) -> Alerta | None:
    """Alerta persistida con los hallazgos del corte actual (si la causa sigue detectándose)."""
    persistida = persistencia_service.obtener_alerta(alerta_id)
    corte = persistencia_service.obtener_reloj()["corte"]
    vivas = _alertas_vivas(corte)
    if persistida is None:
        return next((a for a in vivas if a.alerta_id == alerta_id), None)
    viva = next((a for a in vivas if a.huella_causa == persistida.huella_causa), None)
    if viva is None:
        return persistida
    return persistida.model_copy(
        update={
            "hallazgos": viva.hallazgos,
            "severidad": viva.severidad,
            "dinero_en_riesgo_cop": viva.dinero_en_riesgo_cop,
        }
    )


# -----------------------------------------------------------------------------
# Salud
# -----------------------------------------------------------------------------
@app.get("/health", tags=["Salud"])
def health():
    return {"status": "ok", "version": app.version, "servicio": "centinela"}


# -----------------------------------------------------------------------------
# Reloj simulado
# -----------------------------------------------------------------------------
@app.get("/simulacion/corte", tags=["Simulacion"])
def obtener_corte():
    estado = persistencia_service.obtener_reloj()
    return {
        "corte": estado["corte"],
        "corte_inicial_limpio": CORTE_INICIAL_LIMPIO,
        "corte_maximo": FECHA_CORTE_DEFECTO,
        "run_id": estado["run_id"],
        "actualizado_en": estado["actualizado_en"],
    }


@app.post("/simulacion/avanzar", response_model=SimulacionResp, tags=["Simulacion"])
def avanzar_simulacion(
    request: Request,
    dias: int = Query(None, ge=1, le=365, description="Número de días a avanzar"),
    body: dict[str, Any] | None = Body(None),
):
    """Mueve el reloj, ejecuta el Vigía al nuevo corte y persiste las causas detectadas por primera vez."""
    num_dias = dias
    if num_dias is None and body and "dias" in body:
        try:
            num_dias = int(body["dias"])
        except (ValueError, TypeError):
            return _error(request, "validacion", "El campo 'dias' debe ser un entero.", 400)
    if num_dias is None or not 1 <= num_dias <= 365:
        return _error(request, "validacion", "Debe especificar 'dias' entre 1 y 365.", 400)

    nuevo_corte = persistencia_service.obtener_reloj()["corte"] + timedelta(days=num_dias)
    if nuevo_corte > FECHA_CORTE_DEFECTO:
        return JSONResponse(
            status_code=400,
            content={
                "detail": f"El corte simulado ({nuevo_corte}) supera la fecha maxima permitida ({FECHA_CORTE_DEFECTO}).",
            },
        )

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    persistencia_service.actualizar_reloj(nuevo_corte, run_id)
    antes = len(persistencia_service.alertas_por_huella())
    sincronizadas = _alertas_sincronizadas(nuevo_corte, crear=True)
    despues = len(persistencia_service.alertas_por_huella())
    return SimulacionResp(
        run_id=run_id,
        corte=nuevo_corte,
        dias_avanzados=num_dias,
        alertas_detectadas=len(sincronizadas),
        alertas_nuevas=max(despues - antes, 0),
    )


@app.post("/simulacion/reiniciar", response_model=SimulacionResp, tags=["Simulacion"])
def reiniciar_simulacion():
    """Vuelve al corte inicial limpio y borra alertas, propuestas, trazas y rechazos de la demo (no la bitácora)."""
    borrados = persistencia_service.borrar_estado_demo()
    _vivas_cache.clear()
    estado = persistencia_service.reiniciar_reloj()
    log_evento("INFO", "simulacion.reiniciada", agente="api", **borrados)
    return SimulacionResp(run_id=estado["run_id"], corte=estado["corte"], dias_avanzados=0)


# -----------------------------------------------------------------------------
# Alertas
# -----------------------------------------------------------------------------
@app.get("/alertas", response_model=list[AlertaVista], tags=["Alertas"])
def listar_alertas(
    estado: str | None = Query(None, description="Filtrar por estado (p. ej. 'nueva', 'propuesta')"),
    corte: date | None = Query(None, description="Evalúa al corte indicado sin persistir (pruebas)"),
    persistir: bool = Query(False, description="Con `corte`, persiste las causas nuevas"),
):
    """Una alerta por causa al corte actual, con estado, propuesta y nombres resueltos."""
    fecha_eval = corte or persistencia_service.obtener_reloj()["corte"]
    alertas = _alertas_sincronizadas(fecha_eval, crear=corte is None or persistir)
    if estado:
        alertas = [a for a in alertas if a.estado.value == estado]
    return _vistas(alertas)


@app.get("/alertas/resumen", response_model=ResumenAlertas, tags=["Alertas"])
def resumen_alertas():
    """Dinero en riesgo (una alerta por causa, sin doble conteo) y las tres decisiones clave."""
    corte = persistencia_service.obtener_reloj()["corte"]
    alertas = _alertas_sincronizadas(corte, crear=True)
    pendientes = [a for a in alertas if a.estado in ESTADOS_PENDIENTES]
    resueltas = [a for a in alertas if a.estado in ESTADOS_RESUELTOS]

    # Decisiones clave: la mayor alerta de cada familia de causa (costo/margen, cartera, inactividad...), hasta tres.
    clave: list[Alerta] = []
    familias: set[str] = set()
    for a in sorted(pendientes, key=lambda x: x.dinero_en_riesgo_cop, reverse=True):
        familia = a.huella_causa.split("|", 1)[0]
        if familia in familias:
            continue
        familias.add(familia)
        clave.append(a)
        if len(clave) == 3:
            break

    por_severidad: dict[str, int] = {}
    for a in pendientes:
        por_severidad[a.severidad.value] = por_severidad.get(a.severidad.value, 0) + 1

    return ResumenAlertas(
        corte=corte,
        total_dinero_en_riesgo_cop=sum(a.dinero_en_riesgo_cop for a in pendientes),
        pendientes=len(pendientes),
        resueltas=len(resueltas),
        por_severidad=por_severidad,
        decisiones_clave=_vistas(clave),
    )


@app.get("/alertas/{alerta_id}", response_model=AlertaVista, tags=["Alertas"])
def obtener_alerta_detalle(alerta_id: str, request: Request, response: Response):
    alerta = _alerta_actual(alerta_id)
    if not alerta:
        return _error(request, "no_encontrado", f"Alerta '{alerta_id}' no encontrada.", 404)
    response.headers["ETag"] = f'"{alerta.version}"'
    return _vistas([alerta])[0]


@app.post("/alertas/{alerta_id}/procesar", response_model=AlertaVista, tags=["Alertas"])
async def procesar_alerta_endpoint(alerta_id: str, request: Request, response: Response):
    """Analista y Estratega sobre una alerta: nueva -> en_analisis -> propuesta (idempotente)."""
    alerta = _alerta_actual(alerta_id)
    if not alerta:
        return _error(request, "no_encontrado", f"Alerta '{alerta_id}' no encontrada.", 404)
    if persistencia_service.obtener_alerta(alerta_id) is None:
        persistencia_service.persistir_alertas_nuevas([alerta])
    else:
        persistencia_service.actualizar_alerta(alerta)   # refresca hallazgos al corte actual
    corte = persistencia_service.obtener_reloj()["corte"]
    try:
        alerta_act, _ = await procesar_alerta_completa(alerta_id, corte=corte)
    except Exception as e:  # noqa: BLE001
        logger.exception("Fallo procesando %s", alerta_id)
        return _error(request, "interno", f"No se pudo procesar la alerta: {e}", 500)
    response.headers["ETag"] = f'"{alerta_act.version}"'
    return _vistas([alerta_act])[0]


@app.post("/alertas/{alerta_id}/reabrir", response_model=AlertaVista, tags=["Alertas"])
def reabrir_alerta_endpoint(alerta_id: str, request: Request, actor: str = Query(..., pattern=r"^usuario:[a-z0-9_.-]{2,30}$")):
    """Vuelve a `nueva` una alerta rechazada para que Centinela proponga de nuevo teniendo en cuenta el rechazo."""
    try:
        alerta = reabrir_alerta(alerta_id, actor)
    except ValueError as e:
        return _error(request, "transicion_invalida", str(e), 409)
    return _vistas([alerta])[0]


@app.post("/alertas/{alerta_id}/decision", tags=["Alertas"])
def tomar_decision_endpoint(alerta_id: str, decision: DecisionRequest, request: Request, response: Response):
    """Aprueba, edita o rechaza. Exige `Idempotency-Key`; soporta `If-Match: <versión>`."""
    if not request.headers.get("Idempotency-Key"):
        return _error(request, "validacion", "La cabecera 'Idempotency-Key' es obligatoria para registrar decisiones.", 400)

    version_previa = None
    if_match = request.headers.get("If-Match")
    if if_match:
        try:
            version_previa = int(if_match.strip('"').strip())
        except ValueError:
            return _error(request, "validacion", "La cabecera 'If-Match' debe contener un número de versión válido.", 400)

    alerta = persistencia_service.obtener_alerta(alerta_id)
    if not alerta:
        return _error(request, "no_encontrado", f"Alerta '{alerta_id}' no encontrada.", 404)

    if alerta.estado in (EstadoAlerta.APROBADA, EstadoAlerta.EJECUTADA, EstadoAlerta.RECHAZADA):
        previo = persistencia_service.obtener_resultado_ejecucion(alerta_id)
        if previo:
            return {"alerta": alerta.model_dump(mode="json"), "resultado": previo.model_dump(mode="json")}

    if version_previa is not None and alerta.version != version_previa:
        return _error(
            request,
            "conflicto_version",
            f"Conflicto de versión optimista: versión actual es {alerta.version}, esperada {version_previa}.",
            409,
            {"version_actual": alerta.version, "version_esperada": version_previa},
        )
    if alerta.estado != EstadoAlerta.PROPUESTA:
        return _error(
            request,
            "transicion_invalida",
            f"Transición inválida desde estado '{alerta.estado.value}'. Solo se permiten decisiones en estado 'propuesta'.",
            409,
            {"estado_actual": alerta.estado.value},
        )

    try:
        alerta_final, resultado = aplicar_decision_humana(alerta_id=alerta_id, decision=decision, version_previa=version_previa)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error aplicando decisión de %s", alerta_id)
        return _error(request, "interno", f"Error al ejecutar la decisión humana: {e}", 500)

    emitir_decision_humana(str(decision.decision))
    log_evento("INFO", "hitl.decision_aplicada", agente="hitl", alerta_id=alerta_id, decision=str(decision.decision), actor=decision.decidido_por)
    response.headers["ETag"] = f'"{alerta_final.version}"'
    return {"alerta": alerta_final.model_dump(mode="json"), "resultado": resultado.model_dump(mode="json")}


# -----------------------------------------------------------------------------
# Consultas registradas ("Cómo llegué aquí")
# -----------------------------------------------------------------------------
@app.get("/consultas/{consulta_id}", tags=["Consultas"])
def obtener_consulta(consulta_id: str, request: Request):
    consulta = persistencia_service.obtener_consulta(consulta_id) or consulta_en_cache(consulta_id)
    if consulta is None:
        return _error(request, "no_encontrado", f"Consulta '{consulta_id}' no encontrada.", 404)
    return consulta.model_dump(mode="json")


# -----------------------------------------------------------------------------
# Bitácora
# -----------------------------------------------------------------------------
@app.get("/bitacora", tags=["Bitacora"])
def consultar_bitacora(
    alerta_id: str | None = Query(None, description="Si se omite, devuelve la auditoría general"),
    verificar: bool = Query(False, description="Verifica la cadena SHA-256 (solo con alerta_id)"),
    actor: str | None = Query(None),
    evento: str | None = Query(None),
    limite: int = Query(100, ge=1, le=500),
):
    """Auditoría de una alerta (con verificación de cadena) o general (quién hizo qué y cuándo)."""
    if alerta_id is None:
        entradas = persistencia_service.listar_bitacora(limite=limite, actor=actor, evento=evento)
        return {
            "alerta_id": None,
            "total_entradas": len(entradas),
            "cadena_valida": True,
            "entradas": [e.model_dump(mode="json") for e in entradas],
        }

    entradas = persistencia_service.obtener_bitacora(alerta_id)
    cadena_valida = True
    if verificar and entradas:
        cadena_valida = verificar_cadena(entradas)
        if not cadena_valida:
            emitir_bitacora_cadena_rota(tipo="sha256_o_secuencia_invalida")
            log_evento("CRITICAL", "bitacora.cadena_rota", agente="bitacora", alerta_id=alerta_id, tipo="sha256_o_secuencia_invalida")
    return {
        "alerta_id": alerta_id,
        "total_entradas": len(entradas),
        "cadena_valida": cadena_valida,
        "entradas": [e.model_dump(mode="json") for e in entradas],
    }


@app.get("/bitacora/{alerta_id}", tags=["Bitacora"], include_in_schema=False)
def consultar_bitacora_por_ruta(alerta_id: str, verificar: bool = Query(False)):
    return consultar_bitacora(alerta_id=alerta_id, verificar=verificar, actor=None, evento=None, limite=500)


# -----------------------------------------------------------------------------
# Configuración del Vigía
# -----------------------------------------------------------------------------
def _configuracion_vigente() -> ConfiguracionVigia:
    actuales = asdict(cargar_umbrales())
    defecto = asdict(Umbrales())
    umbrales = [
        ConfigUmbral(
            nombre=nombre,
            etiqueta=meta["etiqueta"],
            kpi=meta["kpi"],
            unidad=meta["unidad"],
            politica=meta["politica"],
            valor=float(actuales[nombre]),
            defecto=float(defecto[nombre]),
            minimo=float(meta["min"]),
            maximo=float(meta["max"]),
        )
        for nombre, meta in META_UMBRALES.items()
    ]
    return ConfiguracionVigia(umbrales=umbrales, autonomia=cargar_autonomia())


@app.get("/config", response_model=ConfiguracionVigia, tags=["Configuracion"])
def obtener_configuracion():
    return _configuracion_vigente()


@app.put("/config", response_model=ConfiguracionVigia, tags=["Configuracion"])
def actualizar_configuracion(cambios: ConfiguracionUpdate, request: Request):
    """Cambia umbrales y autonomía. El Vigía usa los nuevos valores desde el siguiente cálculo."""
    try:
        if cambios.umbrales:
            guardar_umbrales(cambios.umbrales, cambios.actor)
        if cambios.autonomia:
            guardar_autonomia(cambios.autonomia, cambios.actor)
    except ConfiguracionInvalida as e:
        return _error(request, "validacion", str(e), 422)
    _vivas_cache.clear()
    log_evento("INFO", "config.actualizada", agente="api", actor=cambios.actor, umbrales=list(cambios.umbrales), autonomia=list(cambios.autonomia))
    return _configuracion_vigente()


# -----------------------------------------------------------------------------
# Chat (SSE)
# -----------------------------------------------------------------------------
@app.post("/chat", tags=["Chat"])
async def chat_endpoint(request: ChatRequest):
    """Chat anclado a una alerta o libre, con streaming Server-Sent Events."""
    return StreamingResponse(
        generar_respuesta_chat_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
