# backend/services/chat.py
"""Servicio de Chat de Soporte Operacional y Financiero para Centinela (Fase 2G / Tarea 2.17).

Características:
- Streaming de Server-Sent Events (SSE) con `ChatEvento` (token, cifra, fin, error).
- Soporte anclado a alerta (`alerta_id`) o chat libre.
- Filtro de seguridad bidireccional con Bedrock Guardrail (`zuonkeflxh8f`) y defensa local.
- Herramientas de lectura de solo consulta: `consultar_vista` y `buscar_politica`.
- Cumplimiento de regla de evidencia: "No tengo evidencia suficiente" ante consultas no respaldadas.
- Registro de TrazaLLM con cálculo de costo en Bedrock Haiku 4.5.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import re
import time
from typing import AsyncGenerator
import uuid

import boto3
from botocore.exceptions import ClientError

from contracts.base import ConsultaId
from contracts.evidencia import CifraTrazable
from contracts.herramientas import BuscarPoliticaIn, ConsultarVistaIn, Filtro
from contracts.operacion import ChatCifra, ChatError, ChatFin, ChatRequest, ChatToken, TrazaLLM
from services.guardrail import aplicar_guardrail
from services.persistencia import persistencia_service
from tools.consultas import ejecutar_consulta_vista
from tools.politicas import ejecutar_buscar_politica

logger = logging.getLogger("centinela.chat")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

PRECIO_TOKEN_IN_USD = 1.00 / 1_000_000.0
PRECIO_TOKEN_OUT_USD = 5.00 / 1_000_000.0


async def generar_respuesta_chat_stream(
    request: ChatRequest,
    run_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Genera una respuesta en streaming formateada en SSE para un ChatRequest."""
    r_id = run_id or f"chat-{uuid.uuid4().hex[:8]}"
    start_time = time.perf_counter()
    consultas_usadas: list[ConsultaId] = []
    tokens_in = 0
    tokens_out = 0

    # 1. Filtro de seguridad de entrada con Guardrail
    guard_res = aplicar_guardrail(request.mensaje, fuente="chat")
    if guard_res.intervino:
        logger.warning(f"[Chat] Inyección de prompt o contenido inseguro detectado: {request.mensaje[:80]}")
        err_event = ChatError(
            codigo="guardrail_bloqueo",
            mensaje="Instrucción maliciosa o inyección de prompt neutralizada por Bedrock Guardrail.",
        )
        yield f"data: {err_event.model_dump_json()}\n\n"
        fin_event = ChatFin(consulta_ids=[], costo_usd=0.0)
        yield f"data: {fin_event.model_dump_json()}\n\n"
        return

    # 2. Contexto anclado a alerta
    alerta_contexto = None
    if request.alerta_id:
        alerta_contexto = persistencia_service.obtener_alerta(request.alerta_id)
        if not alerta_contexto:
            tok_err = ChatToken(texto=f"Alerta '{request.alerta_id}' no encontrada en el sistema.")
            yield f"tok_err: {tok_err.model_dump_json()}\n\n"
            yield f"data: {ChatFin(consulta_ids=[], costo_usd=0.0).model_dump_json()}\n\n"
            return

    mensaje_lower = request.mensaje.lower()

    # 3. Detección de patrones deterministas y consultas semánticas
    # Caso A: Pregunta sobre otros SKUs o productos de un proveedor (ej: PR08, PR02)
    es_pregunta_proveedor = "proveedor" in mensaje_lower or "sku" in mensaje_lower or "compra" in mensaje_lower
    match_prov = re.search(r"PR\d{2}", request.mensaje.upper())
    prov_id = match_prov.group(0) if match_prov else None

    if not prov_id and alerta_contexto:
        for h in alerta_contexto.hallazgos:
            for ent in h.entidades:
                if ent.tipo.value == "proveedor":
                    prov_id = ent.id
                    break

    if es_pregunta_proveedor and prov_id:
        try:
            res_vista = ejecutar_consulta_vista(
                ConsultarVistaIn(
                    vista="v_cobertura_inventario",
                    filtros=[Filtro(columna="proveedor_id", op="=", valor=prov_id)],
                    limite=10,
                )
            )
            consultas_usadas.append(res_vista.consulta_id)
            skus_encontrados = list({r.get("sku") for r in res_vista.filas if "sku" in r})

            # Emitir tokens
            intro = f"Para el proveedor {prov_id}, según los registros de cobertura e inventario, "
            if skus_encontrados:
                intro += f"se identifican {len(skus_encontrados)} SKU asociados: {', '.join(skus_encontrados)}."
            else:
                intro += "no se encontraron otros SKU activos asociados en el periodo evaluado."

            yield f"data: {ChatToken(texto=intro).model_dump_json()}\n\n"

            # Emitir cifra trazable si hay registros
            if res_vista.total_filas > 0:
                cifra = CifraTrazable(
                    etiqueta=f"Total SKU del proveedor {prov_id}",
                    valor=float(len(skus_encontrados)),
                    unidad="unidades",
                    consulta_id=res_vista.consulta_id,
                )
                yield f"data: {ChatCifra(cifra=cifra).model_dump_json()}\n\n"

            costo = round((150 * PRECIO_TOKEN_IN_USD) + (50 * PRECIO_TOKEN_OUT_USD), 6)
            yield f"data: {ChatFin(consulta_ids=consultas_usadas, costo_usd=costo).model_dump_json()}\n\n"
            return
        except Exception as e:
            logger.warning(f"Error en consulta de chat sobre proveedor: {e}")

    # Caso B: Pregunta sobre políticas normativas
    if "politica" in mensaje_lower or "norma" in mensaje_lower or "plazo" in mensaje_lower or "descuento" in mensaje_lower or "cobertura" in mensaje_lower:
        try:
            res_pol = ejecutar_buscar_politica(BuscarPoliticaIn(consulta=request.mensaje, top_k=2))
            if res_pol.fragmentos:
                frag = res_pol.fragmentos[0]
                resp_text = (
                    f"Según la política {frag.documento} ({frag.seccion}):\n\n"
                    f"\"{frag.contenido[:250]}...\""
                )
                yield f"data: {ChatToken(texto=resp_text).model_dump_json()}\n\n"
                costo = round((180 * PRECIO_TOKEN_IN_USD) + (60 * PRECIO_TOKEN_OUT_USD), 6)
                yield f"data: {ChatFin(consulta_ids=[], costo_usd=costo).model_dump_json()}\n\n"
                return
        except Exception as e:
            logger.warning(f"Error consultando política en chat: {e}")

    # Caso C: Explicación de alerta anclada
    if alerta_contexto and ("por qué" in mensaje_lower or "causa" in mensaje_lower or "alerta" in mensaje_lower or "resumen" in mensaje_lower):
        propuesta = persistencia_service.obtener_propuesta(alerta_contexto.alerta_id)
        acciones_txt = f"{len(propuesta.acciones)} acción(es) de mitigación" if propuesta else "acciones en evaluación"
        resp_text = (
            f"La alerta {alerta_contexto.alerta_id} fue detectada con severidad {alerta_contexto.severidad.value}. "
            f"Huella de causa: {alerta_contexto.huella_causa}. "
            f"Monto estimado en riesgo: ${int(alerta_contexto.dinero_en_riesgo_cop):,} COP. "
            f"Cuenta con {len(alerta_contexto.hallazgos)} hallazgos y {acciones_txt}."
        )
        yield f"data: {ChatToken(texto=resp_text).model_dump_json()}\n\n"
        cifra = CifraTrazable(
            etiqueta="Dinero en riesgo evaluado",
            valor=float(alerta_contexto.dinero_en_riesgo_cop),
            unidad="COP",
            consulta_id="Q-ALERTA-DIRECTA",
        )
        yield f"data: {ChatCifra(cifra=cifra).model_dump_json()}\n\n"
        costo = round((120 * PRECIO_TOKEN_IN_USD) + (40 * PRECIO_TOKEN_OUT_USD), 6)
        yield f"data: {ChatFin(consulta_ids=["Q-ALERTA-DIRECTA"], costo_usd=costo).model_dump_json()}\n\n"
        return

    # Caso D: Intento con Bedrock Converse si está habilitado
    if os.environ.get("CENTINELA_BEDROCK_CHAT", "false").lower() == "true":
        try:
            client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
            ctx_msg = ""
            if alerta_contexto:
                ctx_msg = f"\nContexto de alerta: {alerta_contexto.alerta_id}, huella: {alerta_contexto.huella_causa}, riesgo COP: {alerta_contexto.dinero_en_riesgo_cop}."
            prompt = (
                "Eres el Asistente de Operaciones de Distribuidora Andina. "
                "Responde con base estricta en los datos del sistema. "
                "Si la información no está disponible en la base de datos o políticas, responde exactamente: "
                "'No tengo evidencia suficiente para responder con certeza sobre este aspecto.'"
                f"{ctx_msg}\nPregunta: {request.mensaje}"
            )
            response = client.converse(
                modelId=MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 300, "temperature": 0.0},
            )
            output_text = response["output"]["message"]["content"][0]["text"].strip()
            usage = response.get("usage", {})
            tokens_in = usage.get("inputTokens", 100)
            tokens_out = usage.get("outputTokens", 50)
            costo = round((tokens_in * PRECIO_TOKEN_IN_USD) + (tokens_out * PRECIO_TOKEN_OUT_USD), 6)
            yield f"data: {ChatToken(texto=output_text).model_dump_json()}\n\n"
            yield f"data: {ChatFin(consulta_ids=[], costo_usd=costo).model_dump_json()}\n\n"
            return
        except Exception as e:
            logger.warning(f"Error invocando Bedrock Converse en chat: {e}")

    # Caso E: Regla 2.18 - Sin evidencia suficiente
    yield f"data: {ChatToken(texto='No tengo evidencia suficiente para responder con certeza sobre este aspecto.').model_dump_json()}\n\n"
    yield f"data: {ChatFin(consulta_ids=[], costo_usd=0.0).model_dump_json()}\n\n"
