# backend/services/telemetry.py
"""Servicio de Telemetría, Logging JSON estructurado y Métricas CloudWatch EMF (Embedded Metric Format).

Implementa las directrices de Fase 3b de Centinela (docs/05_monitorizacion.md):
- Logging estructurado JSON: {ts, nivel, request_id, run_id, alerta_id, agente, evento}
- Cero PII y cero cifras de negocio en logs (estricta sanitización y trazabilidad por IDs técnicos).
- CloudWatch Embedded Metric Format (EMF) en el namespace 'Centinela' para ingesta
  automática asíncrona sin llamadas adicionales ni costos de API de CloudWatch.

Métricas clave emitidas:
- AlertasGeneradas (Dimensions: [Kpi, Severidad], Unit: Count)
- PipelineLatenciaMs (Dimensions: [Agente], Unit: Milliseconds)
- LlmTokensEntrada (Dimensions: [Agente], Unit: Count)
- LlmTokensSalida (Dimensions: [Agente], Unit: Count)
- CostoUsdPorAlerta (Dimensions: [Agente], Unit: None)
- ValidacionFallida (Dimensions: [Agente], Unit: Count)
- ReintentosLlm (Dimensions: [Agente], Unit: Count)
- SinEvidencia (Dimensions: [Agente], Unit: Count)
- GuardrailIntervino (Dimensions: [Tipo], Unit: Count)
- BitacoraCadenaRota (Dimensions: [Tipo], Unit: Count)
- AprobacionesHumanas / Rechazos (Dimensions: [Decision], Unit: Count)
"""

from __future__ import annotations

import contextvars
from datetime import datetime, timezone
import json
import logging
import sys
import time
from typing import Any, Callable

logger = logging.getLogger("centinela.telemetry")

# -----------------------------------------------------------------------------
# Variables de Contexto Asíncrono para Trazabilidad Distribuida
# -----------------------------------------------------------------------------
ctx_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("ctx_request_id", default="req-unknown")
ctx_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("ctx_run_id", default="run-unknown")
ctx_alerta_id: contextvars.ContextVar[str] = contextvars.ContextVar("ctx_alerta_id", default="ALR-none")
ctx_agente: contextvars.ContextVar[str] = contextvars.ContextVar("ctx_agente", default="sistema")

# Lista de claves prohibidas por seguridad y privacidad (PII y cifras de negocio libres)
CAMPOS_PROHIBIDOS = {
    "nombre", "cliente_nombre", "vendedor_nombre", "proveedor_nombre",
    "email", "correo", "telefono", "direccion", "cedula", "nit",
    "saldo", "saldo_cop", "monto", "dinero", "precio", "costo",
    "dinero_en_riesgo", "dinero_en_riesgo_cop", "valor_neto"
}


def sanitizar_datos_log(datos: dict[str, Any]) -> dict[str, Any]:
    """Elimina o anonimiza cualquier campo susceptible de contener PII o cifras de negocio libres.

    Solo conserva IDs técnicos, nombres de evento, estados y métricas operativas.
    """
    limpio: dict[str, Any] = {}
    for k, v in datos.items():
        k_lower = k.lower()
        if any(prohibido in k_lower for prohibido in CAMPOS_PROHIBIDOS):
            continue
        # Sanitizar valores de tipo string para prevenir inyecciones accidentales
        if isinstance(v, str) and len(v) > 300:
            limpio[k] = v[:297] + "..."
        else:
            limpio[k] = v
    return limpio


def log_evento(
    nivel: str,
    evento: str,
    agente: str | None = None,
    alerta_id: str | None = None,
    run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Emite un registro de log JSON estructurado estándar de Centinela.

    Formato:
    {
      "ts": "2026-10-03T18:00:00.000Z",
      "nivel": "INFO",
      "request_id": "req-...",
      "run_id": "run-...",
      "alerta_id": "ALR-...",
      "agente": "vigia",
      "evento": "vigia.alertas_detectadas",
      ...metadatos_sanitizados...
    }
    """
    ts = datetime.now(timezone.utc).isoformat()
    req_id = ctx_request_id.get()
    r_id = run_id or ctx_run_id.get()
    a_id = alerta_id or ctx_alerta_id.get()
    ag = agente or ctx_agente.get()

    datos_extra = sanitizar_datos_log(kwargs)

    entrada = {
        "ts": ts,
        "nivel": nivel.upper(),
        "request_id": req_id,
        "run_id": r_id,
        "alerta_id": a_id,
        "agente": ag,
        "evento": evento,
        **datos_extra,
    }

    mensaje_json = json.dumps(entrada, ensure_ascii=False, default=str)
    
    # Imprimir en el nivel correspondiente
    if nivel.upper() == "DEBUG":
        logger.debug(mensaje_json)
    elif nivel.upper() == "WARNING":
        logger.warning(mensaje_json)
    elif nivel.upper() in ("ERROR", "CRITICAL"):
        logger.error(mensaje_json)
    else:
        logger.info(mensaje_json)

    return entrada


# -----------------------------------------------------------------------------
# Motor de Métricas CloudWatch Embedded Metric Format (EMF)
# -----------------------------------------------------------------------------
def emitir_metrica_emf(
    namespace: str,
    dimensiones: list[list[str]],
    metricas: list[dict[str, str]],
    valores: dict[str, Any],
    propiedades: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Genera y emite un registro compatible con AWS CloudWatch Embedded Metric Format (EMF).

    CloudWatch Logs procesa de forma nativa este formato asíncronamente y publica
    las métricas en el Namespace especificado sin costos adicionales de PutMetricData.
    """
    timestamp_ms = int(time.time() * 1000)

    registro_emf: dict[str, Any] = {
        "_aws": {
            "Timestamp": timestamp_ms,
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": dimensiones,
                    "Metrics": metricas,
                }
            ],
        },
        **valores,
    }

    if propiedades:
        registro_emf.update(sanitizar_datos_log(propiedades))

    mensaje_emf = json.dumps(registro_emf, ensure_ascii=False, default=str)
    # Escribir directamente al logger para captura por CloudWatch Logs
    logger.info(mensaje_emf)
    return registro_emf


# -----------------------------------------------------------------------------
# Emisores Específicos para Métricas de Negocio y Operación Centinela
# -----------------------------------------------------------------------------
def emitir_alertas_generadas(kpi: str, severidad: str, count: int = 1) -> dict[str, Any]:
    """Emite métrica EMF 'AlertasGeneradas' con dimensiones [Kpi, Severidad]."""
    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Kpi", "Severidad"]],
        metricas=[{"Name": "AlertasGeneradas", "Unit": "Count"}],
        valores={
            "Kpi": str(kpi),
            "Severidad": str(severidad),
            "AlertasGeneradas": int(count),
        },
        propiedades={"evento": "vigia.alerta_emitida"},
    )


def emitir_pipeline_latencia(agente: str, latencia_ms: float) -> dict[str, Any]:
    """Emite métrica EMF 'PipelineLatenciaMs' con dimensión [Agente]."""
    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Agente"]],
        metricas=[{"Name": "PipelineLatenciaMs", "Unit": "Milliseconds"}],
        valores={
            "Agente": str(agente),
            "PipelineLatenciaMs": round(float(latencia_ms), 2),
        },
        propiedades={"evento": f"{agente}.latencia_pipeline"},
    )


def emitir_llm_tokens(
    agente: str,
    tokens_in: int,
    tokens_out: int,
    costo_usd: float = 0.0,
) -> dict[str, Any]:
    """Emite métricas EMF de consumo de tokens y costo en USD para Bedrock Claude Haiku 4.5."""
    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Agente"]],
        metricas=[
            {"Name": "LlmTokensEntrada", "Unit": "Count"},
            {"Name": "LlmTokensSalida", "Unit": "Count"},
            {"Name": "CostoUsdPorAlerta", "Unit": "None"},
        ],
        valores={
            "Agente": str(agente),
            "LlmTokensEntrada": int(tokens_in),
            "LlmTokensSalida": int(tokens_out),
            "CostoUsdPorAlerta": round(float(costo_usd), 6),
        },
        propiedades={"evento": f"{agente}.consumo_llm"},
    )


def emitir_validacion_fallida(agente: str) -> dict[str, Any]:
    """Emite métrica EMF 'ValidacionFallida' cuando un contrato Pydantic rechaza datos."""
    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Agente"]],
        metricas=[{"Name": "ValidacionFallida", "Unit": "Count"}],
        valores={"Agente": str(agente), "ValidacionFallida": 1},
        propiedades={"evento": f"{agente}.validacion_pydantic_error"},
    )


def emitir_reintentos_llm(agente: str) -> dict[str, Any]:
    """Emite métrica EMF 'ReintentosLlm' cuando se requiere un segundo turno de corrección."""
    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Agente"]],
        metricas=[{"Name": "ReintentosLlm", "Unit": "Count"}],
        valores={"Agente": str(agente), "ReintentosLlm": 1},
        propiedades={"evento": f"{agente}.reintento_llm"},
    )


def emitir_sin_evidencia(agente: str = "analista") -> dict[str, Any]:
    """Emite métrica EMF 'SinEvidencia' cuando el modelo reporta evidencia insuficiente."""
    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Agente"]],
        metricas=[{"Name": "SinEvidencia", "Unit": "Count"}],
        valores={"Agente": str(agente), "SinEvidencia": 1},
        propiedades={"evento": f"{agente}.sin_evidencia_suficiente"},
    )


def emitir_guardrail_intervino(tipo: str) -> dict[str, Any]:
    """Emite métrica EMF 'GuardrailIntervino' clasificada por Tipo ('ataque' o 'pii')."""
    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Tipo"]],
        metricas=[{"Name": "GuardrailIntervino", "Unit": "Count"}],
        valores={"Tipo": str(tipo), "GuardrailIntervino": 1},
        propiedades={"evento": "guardrail.intervencion"},
    )


def emitir_bitacora_cadena_rota(tipo: str = "inconsistencia") -> dict[str, Any]:
    """Emite métrica EMF crítica 'BitacoraCadenaRota' cuando se detecta manipulación en la cadena."""
    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Tipo"]],
        metricas=[{"Name": "BitacoraCadenaRota", "Unit": "Count"}],
        valores={"Tipo": str(tipo), "BitacoraCadenaRota": 1},
        propiedades={"evento": "bitacora.cadena_rota_critica"},
    )


def emitir_decision_humana(decision: str) -> dict[str, Any]:
    """Emite métrica EMF 'AprobacionesHumanas' o 'Rechazos' según la decisión del usuario."""
    dec_lower = decision.lower()
    if "aprob" in dec_lower:
        nombre_metrica = "AprobacionesHumanas"
    elif "rechaz" in dec_lower:
        nombre_metrica = "Rechazos"
    else:
        nombre_metrica = "EdicionesHumanas"

    return emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Decision"]],
        metricas=[{"Name": nombre_metrica, "Unit": "Count"}],
        valores={"Decision": str(decision), nombre_metrica: 1},
        propiedades={"evento": f"hitl.decision_{dec_lower}"},
    )


# -----------------------------------------------------------------------------
# Context Manager para Medición Precisa de Latencia
# -----------------------------------------------------------------------------
class MedidorLatencia:
    """Context manager para cronometrar bloques de ejecución de agentes y emitir EMF."""

    def __init__(self, agente: str):
        self.agente = agente
        self.inicio: float = 0.0
        self.latencia_ms: float = 0.0

    def __enter__(self) -> MedidorLatencia:
        self.inicio = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.latencia_ms = (time.perf_counter() - self.inicio) * 1000.0
        emitir_pipeline_latencia(self.agente, self.latencia_ms)
        log_evento(
            "INFO",
            f"{self.agente}.latencia_completada",
            agente=self.agente,
            latencia_ms=round(self.latencia_ms, 2),
        )
