# backend/services/llm.py
"""Acceso único a Bedrock (Claude Haiku 4.5) con registro de tokens, costo y latencia.

Todas las llamadas de los agentes y del chat pasan por aquí: así el costo por alerta sale de los tokens que
reporta Bedrock (`usage`), no de estimaciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import time
from typing import Any

import boto3

from contracts.operacion import TrazaLLM
from services.persistencia import persistencia_service

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

# Precios de Claude Haiku 4.5 en Bedrock (USD por millón de tokens). Verificar en la página de precios de Bedrock.
PRECIO_ENTRADA_USD_MTOK = float(os.environ.get("PRECIO_ENTRADA_USD_MTOK", "1.00"))
PRECIO_SALIDA_USD_MTOK = float(os.environ.get("PRECIO_SALIDA_USD_MTOK", "5.00"))

_cliente: Any = None


def cliente_bedrock() -> Any:
    global _cliente
    if _cliente is None:
        _cliente = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    return _cliente


def costo_usd(tokens_in: int, tokens_out: int) -> float:
    return round(tokens_in * PRECIO_ENTRADA_USD_MTOK / 1e6 + tokens_out * PRECIO_SALIDA_USD_MTOK / 1e6, 6)


@dataclass(frozen=True)
class RespuestaLLM:
    contenido: list[dict[str, Any]]
    tokens_in: int
    tokens_out: int
    costo_usd: float
    latencia_ms: int

    def tool_use(self, nombre: str) -> dict[str, Any] | None:
        for bloque in self.contenido:
            tu = bloque.get("toolUse")
            if tu and tu.get("name") == nombre:
                return tu.get("input", {})
        return None

    @property
    def texto(self) -> str:
        return "".join(b.get("text", "") for b in self.contenido)


def llamar(
    sistema: str,
    mensajes: list[dict[str, Any]],
    *,
    herramientas: list[dict[str, Any]] | None = None,
    forzar_herramienta: str | None = None,
    max_tokens: int = 1500,
    temperatura: float = 0.0,
) -> RespuestaLLM:
    """Una llamada Converse a Haiku 4.5. Lanza la excepción de boto3 si Bedrock falla."""
    kwargs: dict[str, Any] = {
        "modelId": MODEL_ID,
        "system": [{"text": sistema}],
        "messages": mensajes,
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperatura},
    }
    if herramientas:
        tool_config: dict[str, Any] = {"tools": herramientas}
        if forzar_herramienta:
            tool_config["toolChoice"] = {"tool": {"name": forzar_herramienta}}
        kwargs["toolConfig"] = tool_config
    t0 = time.perf_counter()
    resp = cliente_bedrock().converse(**kwargs)
    latencia = int((time.perf_counter() - t0) * 1000)
    uso = resp.get("usage", {})
    t_in, t_out = int(uso.get("inputTokens", 0)), int(uso.get("outputTokens", 0))
    return RespuestaLLM(
        contenido=resp.get("output", {}).get("message", {}).get("content", []),
        tokens_in=t_in,
        tokens_out=t_out,
        costo_usd=costo_usd(t_in, t_out),
        latencia_ms=latencia,
    )


def mensaje_correccion(resp: RespuestaLLM, texto: str) -> dict[str, Any]:
    """Mensaje de usuario que responde con un error a cada `toolUse` de la respuesta (Converse lo exige)."""
    bloques = [
        {"toolResult": {"toolUseId": b["toolUse"]["toolUseId"], "content": [{"text": texto}], "status": "error"}}
        for b in resp.contenido
        if "toolUse" in b
    ]
    return {"role": "user", "content": bloques or [{"text": texto}]}


def registrar_traza(
    agente: str,
    run_id: str,
    resp: RespuestaLLM | None,
    *,
    alerta_id: str | None = None,
    consulta_ids: list[str] | None = None,
    reintentos: int = 0,
    guardrail_intervino: bool = False,
    error: str | None = None,
) -> TrazaLLM:
    traza = TrazaLLM(
        run_id=run_id,
        alerta_id=alerta_id,
        agente=agente,  # type: ignore[arg-type]
        modelo=MODEL_ID,
        tokens_in=resp.tokens_in if resp else 0,
        tokens_out=resp.tokens_out if resp else 0,
        latencia_ms=resp.latencia_ms if resp else 0,
        costo_usd=resp.costo_usd if resp else 0.0,
        guardrail_intervino=guardrail_intervino,
        consulta_ids=sorted(set(consulta_ids or [])),
        reintentos=reintentos,
        error=error,
        ts=datetime.now(timezone.utc),
    )
    persistencia_service.guardar_traza(traza)
    return traza
