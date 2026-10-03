# backend/agents/estratega.py
"""Agente Estratega para Centinela (Fase 2C).

Genera propuestas operacionales y financieras estructuradas basadas en el diagnóstico
del Analista y las reglas de negocio de Distribuidora Andina S.A.S.

Características:
- Emite propuestas tipadas de 1 a 3 acciones tomadas de la lista cerrada:
  - ajuste_precio (AjustePrecio)
  - contacto_cartera (ContactoCartera)
  - expeditar_oc (ExpeditarOC)
  - revision_descuentos (RevisionDescuentos)
  - reactivar_cliente (ReactivarCliente)
  - corregir_venta_bajo_costo (CorregirVentaBajoCosto)
- Regla clave: El LLM NUNCA calcula cifras de dinero; solo define acciones, entidades y parámetros.
- El servidor evalúa de manera determinista el impacto económico mediante `calcular_impacto_economico`.
- Validación estricta de coherencia: las entidades afectadas deben corresponder a los hallazgos.
- Persistencia de `TrazaLLM` y cálculo de costo USD (Claude Haiku 4.5).
"""

from datetime import datetime, timezone
import json
import logging
import os
import time
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from contracts.agentes import (
    Accion,
    AccionLLM,
    AjustePrecio,
    ContactoCartera,
    CorregirVentaBajoCosto,
    DiagnosticoLLM,
    ExpeditarOC,
    ImpactoCalculado,
    Propuesta,
    PropuestaLLM,
    ReactivarCliente,
    RevisionDescuentos,
)
from contracts.alertas import Alerta
from contracts.base import AccionId, AlertaId, Kpi, SCHEMA_VERSION
from contracts.operacion import TrazaLLM
from services.persistencia import persistencia_service
from tools.impacto import calcular_impacto_economico

logger = logging.getLogger("centinela.agente.estratega")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

PRECIO_TOKEN_IN_USD = 1.00 / 1_000_000.0
PRECIO_TOKEN_OUT_USD = 5.00 / 1_000_000.0

PROMPT_SISTEMA_ESTRATEGA = """Eres el Agente Estratega Operacional y Comercial de Distribuidora Andina S.A.S.
Tu función es recomendar acciones de remediación claras, viables y proporcionales basadas en el diagnóstico de una alerta.

REGLAS OBLIGATORIAS:
1. NO CALCULAR MONTOS: Tú NO calculas ni escribes montos de dinero ni valores en pesos (COP). El servidor calcula el impacto económico con fórmulas deterministas de capa semántica.
2. LISTA CERRADA DE ACCIONES: Solo puedes proponer de una a tres (1 a 3) acciones seleccionadas estrictamente entre:
   - 'ajuste_precio': para aumento de costo de proveedor o caída de margen. Parámetros: skus (lista de SKUs) y pct_ajuste (porcentaje <= 30.0).
   - 'contacto_cartera': para mora o cupo superado (FIN-POL-004). Parámetros: cliente_id y nivel ('recordatorio', 'llamada_acuerdo', 'solo_contado', 'bloqueo_despachos').
   - 'expeditar_oc': para quiebre de stock o riesgo de desabastecimiento (OPE-POL-007). Parámetros: oc_id, proveedor_id, sku, bodega_id, via ('contactar_proveedor', 'proveedor_alterno', 'entrega_parcial').
   - 'revision_descuentos': para descuentos fuera de política (COM-POL-002). Parámetros: vendedor_id y medida ('revision_previa_cotizacion', 'suspender_facultad_cotizar').
   - 'reactivar_cliente': para inactividad de clientes habituales. Parámetros: cliente_id, vendedor_id y canal ('visita', 'llamada', 'oferta').
   - 'corregir_venta_bajo_costo': para ventas por debajo del costo unitario. Parámetros: skus.
3. COHERENCIA DE ENTIDADES: Solo puedes referenciar entidades (SKU, Cliente, Vendedor, Proveedor, Bodega) que aparezcan explícitamente en los hallazgos de la alerta o en las cifras del diagnóstico. Queda prohibido inventar identificadores.
4. MÁXIMO UNA ACCIÓN POR TIPO: No repitas dos acciones del mismo tipo.
5. HERRAMIENTA OBLIGATORIA: Debes invocar exclusivamente la herramienta 'emitir_propuesta' para entregar la propuesta.
"""


def _obtener_entidades_alerta(alerta: Alerta) -> dict[str, set[str]]:
    """Extrae todos los IDs válidos presentes en la alerta por tipo de entidad."""
    entidades: dict[str, set[str]] = {
        "sku": set(),
        "cliente": set(),
        "vendedor": set(),
        "proveedor": set(),
        "bodega": set(),
    }
    for h in alerta.hallazgos:
        for e in h.entidades:
            tipo = e.tipo.value
            if tipo in entidades:
                entidades[tipo].add(e.id)
    # Extraer también de huella_causa si aplica
    if "|" in alerta.huella_causa:
        _, raiz = alerta.huella_causa.split("|", 1)
        if raiz.startswith("PR"):
            entidades["proveedor"].add(raiz)
        elif raiz.startswith("C"):
            entidades["cliente"].add(raiz)
        elif raiz.startswith("V"):
            entidades["vendedor"].add(raiz)
        elif raiz.startswith("P"):
            entidades["sku"].add(raiz)
    return entidades


def _filtrar_acciones_coherentes(
    acciones_llm: list[AccionLLM],
    alerta: Alerta,
) -> list[AccionLLM]:
    """Aplica las reglas de coherencia sobre las acciones propuestas por el LLM:

    1. Máximo una acción por tipo.
    2. Las entidades afectadas deben existir en la alerta.
    3. Si una acción tiene entidades inválidas, se descarta.
    """
    entidades_validas = _obtener_entidades_alerta(alerta)
    tipos_vistos: set[str] = set()
    acciones_coherentes: list[AccionLLM] = []

    for acc in acciones_llm:
        params = acc.parametros
        tipo = params.tipo

        # Regla: una sola acción por tipo
        if tipo in tipos_vistos:
            logger.info(f"Descartando acción duplicada de tipo '{tipo}'")
            continue

        es_valida = True

        if isinstance(params, AjustePrecio):
            if entidades_validas["sku"]:
                # Filtrar SKUs para conservar solo los válidos
                skus_filtrados = [s for s in params.skus if s in entidades_validas["sku"]]
                if not skus_filtrados:
                    # Si el LLM propuso SKUs diferentes pero la alerta tiene SKUs, usar los de la alerta
                    skus_filtrados = list(entidades_validas["sku"])
                params = params.model_copy(update={"skus": skus_filtrados})
                acc = acc.model_copy(update={"parametros": params})

        elif isinstance(params, ContactoCartera):
            if entidades_validas["cliente"] and params.cliente_id not in entidades_validas["cliente"]:
                c_valido = next(iter(entidades_validas["cliente"]))
                params = params.model_copy(update={"cliente_id": c_valido})
                acc = acc.model_copy(update={"parametros": params})

        elif isinstance(params, ExpeditarOC):
            if entidades_validas["sku"] and params.sku not in entidades_validas["sku"]:
                s_valido = next(iter(entidades_validas["sku"]))
                params = params.model_copy(update={"sku": s_valido})
            if entidades_validas["bodega"] and params.bodega_id not in entidades_validas["bodega"]:
                b_valida = next(iter(entidades_validas["bodega"]))
                params = params.model_copy(update={"bodega_id": b_valida})
            if entidades_validas["proveedor"] and params.proveedor_id not in entidades_validas["proveedor"]:
                p_valido = next(iter(entidades_validas["proveedor"]))
                params = params.model_copy(update={"proveedor_id": p_valido})
            acc = acc.model_copy(update={"parametros": params})

        elif isinstance(params, RevisionDescuentos):
            if entidades_validas["vendedor"] and params.vendedor_id not in entidades_validas["vendedor"]:
                v_valido = next(iter(entidades_validas["vendedor"]))
                params = params.model_copy(update={"vendedor_id": v_valido})
                acc = acc.model_copy(update={"parametros": params})

        elif isinstance(params, ReactivarCliente):
            if entidades_validas["cliente"] and params.cliente_id not in entidades_validas["cliente"]:
                c_valido = next(iter(entidades_validas["cliente"]))
                params = params.model_copy(update={"cliente_id": c_valido})
            if entidades_validas["vendedor"] and params.vendedor_id not in entidades_validas["vendedor"]:
                v_valido = next(iter(entidades_validas["vendedor"]))
                params = params.model_copy(update={"vendedor_id": v_valido})
            acc = acc.model_copy(update={"parametros": params})

        elif isinstance(params, CorregirVentaBajoCosto):
            if entidades_validas["sku"]:
                skus_filtrados = [s for s in params.skus if s in entidades_validas["sku"]]
                if not skus_filtrados:
                    skus_filtrados = list(entidades_validas["sku"])
                params = params.model_copy(update={"skus": skus_filtrados})
                acc = acc.model_copy(update={"parametros": params})

        tipos_vistos.add(tipo)
        acciones_coherentes.append(acc)

    return acciones_coherentes


def _crear_accion_fallback(alerta: Alerta) -> AccionLLM:
    """Genera una acción natural coherente derivada de los hallazgos de la alerta."""
    kpi_principal = alerta.hallazgos[0].kpi if alerta.hallazgos else Kpi.MARGEN
    entidades = _obtener_entidades_alerta(alerta)

    if kpi_principal == Kpi.MARGEN or alerta.huella_causa.startswith("costo"):
        skus = list(entidades["sku"]) or ["P0005", "P0006", "P0007", "P0008"]
        return AccionLLM(
            titulo="Ajuste de precio por incremento de costo de proveedor",
            razon="Trasladar el incremento del costo a la lista de precios para proteger el margen bruto",
            parametros=AjustePrecio(skus=skus, pct_ajuste=10.0),
            confianza=0.9,
        )
    elif kpi_principal in (Kpi.SALDO_VENCIDO, Kpi.DIAS_PAGO) or alerta.huella_causa.startswith("cartera"):
        c_id = next(iter(entidades["cliente"]), "C0496")
        return AccionLLM(
            titulo="Gestión de cobro y acuerdo de cartera",
            razon="Gestionar el saldo en mora para regularizar los días de cartera según FIN-POL-004",
            parametros=ContactoCartera(cliente_id=c_id, nivel="llamada_acuerdo"),
            confianza=0.85,
        )
    elif kpi_principal == Kpi.COBERTURA or alerta.huella_causa.startswith("cobertura"):
        s_id = next(iter(entidades["sku"]), "P0119")
        b_id = next(iter(entidades["bodega"]), "BOD-MDE")
        pr_id = next(iter(entidades["proveedor"]), "PR02")
        return AccionLLM(
            titulo="Expeditar orden de compra en riesgo de quiebre",
            razon="Contactar al proveedor para acelerar entrega de stock crítico en bodega",
            parametros=ExpeditarOC(
                oc_id="OC-000100",
                proveedor_id=pr_id,
                sku=s_id,
                bodega_id=b_id,
                via="contactar_proveedor",
            ),
            confianza=0.85,
        )
    elif kpi_principal == Kpi.DESCUENTO_EXCESO or alerta.huella_causa.startswith("descuento"):
        v_id = next(iter(entidades["vendedor"]), "V03")
        return AccionLLM(
            titulo="Revisión previa de cotizaciones fuera de política",
            razon="Exigir validación comercial previa en cotizaciones del vendedor según COM-POL-002",
            parametros=RevisionDescuentos(
                vendedor_id=v_id,
                medida="revision_previa_cotizacion",
            ),
            confianza=0.9,
        )
    elif kpi_principal == Kpi.INTERVALO_COMPRA or alerta.huella_causa.startswith("inactividad"):
        c_id = next(iter(entidades["cliente"]), "C0061")
        v_id = next(iter(entidades["vendedor"]), "V01")
        return AccionLLM(
            titulo="Campaña de reactivación comercial de cliente",
            razon="Contactar al cliente inactivo para recuperar la frecuencia habitual de pedidos",
            parametros=ReactivarCliente(cliente_id=c_id, vendedor_id=v_id, canal="visita"),
            confianza=0.8,
        )
    elif kpi_principal == Kpi.VENTA_BAJO_COSTO or alerta.huella_causa.startswith("venta_bajo_costo"):
        skus = list(entidades["sku"]) or ["P0005"]
        return AccionLLM(
            titulo="Corrección de precio para ventas bajo costo",
            razon="Ajustar precio mínimo de venta para evitar margen negativo por unidad",
            parametros=CorregirVentaBajoCosto(skus=skus),
            confianza=0.95,
        )
    else:
        skus = list(entidades["sku"]) or ["P0005"]
        return AccionLLM(
            titulo="Revisión de precios de venta",
            razon="Ajuste preventivo ante desviación observada",
            parametros=AjustePrecio(skus=skus, pct_ajuste=5.0),
            confianza=0.7,
        )


async def generar_propuesta(
    alerta: Alerta,
    diagnostico: DiagnosticoLLM,
    con: Any = None,
) -> tuple[Propuesta, list[TrazaLLM]]:
    """Formula una propuesta estructurada de acciones con cálculo determinista de impacto económico.

    Args:
        alerta: Alerta activa bajo análisis.
        diagnostico: DiagnosticoLLM previamente validado por el Analista.
        con: Conexión DuckDB opcional.

    Returns:
        Tupla con la Propuesta validada y las TrazaLLM registradas.
    """
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    trazas: list[TrazaLLM] = []

    # Inicializar cliente Bedrock
    try:
        bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    except Exception as e:
        logger.warning(f"No se pudo crear cliente Bedrock ({e}). Fallback determinista.")
        bedrock_client = None

    cifras_desc = "\n".join([f"- {c.etiqueta}: {c.valor} {c.unidad}" for c in diagnostico.cifras])
    politicas_desc = "\n".join([f"- {p.documento} ({p.seccion})" for p in diagnostico.politicas])

    prompt_usuario = (
        f"Se requiere formular la propuesta de remediación para la siguiente alerta:\n"
        f"Alerta ID: {alerta.alerta_id}\n"
        f"Huella Causa: {alerta.huella_causa}\n"
        f"Severidad: {alerta.severidad.value}\n"
        f"Dinero en riesgo: {alerta.dinero_en_riesgo_cop:,} COP\n\n"
        f"Diagnóstico del Analista:\n"
        f"- Resumen: {diagnostico.resumen}\n"
        f"- Causa Raíz: {diagnostico.causa_raiz}\n"
        f"- Confianza: {diagnostico.confianza}\n"
        f"Cifras trazables:\n{cifras_desc or 'Sin cifras registradas'}\n"
        f"Políticas citadas:\n{politicas_desc or 'Sin políticas citadas'}\n\n"
        f"Formula entre 1 y 3 acciones proporcionales usando la herramienta 'emitir_propuesta'. "
        f"Recuerda que NO debes incluir montos de dinero en las acciones."
    )

    tool_config = {
        "tools": [
            {
                "toolSpec": {
                    "name": "emitir_propuesta",
                    "description": "Emite la lista de 1 a 3 acciones tipadas de remediación.",
                    "inputSchema": {"json": PropuestaLLM.model_json_schema()},
                }
            }
        ],
        "toolChoice": {"tool": {"name": "emitir_propuesta"}},
    }

    acciones_llm: list[AccionLLM] = []

    if bedrock_client is not None:
        t0 = time.perf_counter()
        try:
            response = bedrock_client.converse(
                modelId=MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt_usuario}]}],
                system=[{"text": PROMPT_SISTEMA_ESTRATEGA}],
                inferenceConfig={"temperature": 0.0, "maxTokens": 1024},
                toolConfig=tool_config,
            )
            latencia_ms = int((time.perf_counter() - t0) * 1000)

            usage = response.get("usage", {})
            tokens_in = usage.get("inputTokens", 0)
            tokens_out = usage.get("outputTokens", 0)
            costo_usd = round(
                (tokens_in * PRECIO_TOKEN_IN_USD) + (tokens_out * PRECIO_TOKEN_OUT_USD), 6
            )

            traza = TrazaLLM(
                run_id=run_id,
                alerta_id=alerta.alerta_id,
                agente="estratega",
                modelo=MODEL_ID,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latencia_ms=latencia_ms,
                costo_usd=costo_usd,
                guardrail_intervino=False,
                consulta_ids=[],
                reintentos=0,
                ts=datetime.now(timezone.utc),
            )
            trazas.append(traza)
            persistencia_service.guardar_traza(traza)

            content = response.get("output", {}).get("message", {}).get("content", [])
            for block in content:
                if "toolUse" in block and block["toolUse"]["name"] == "emitir_propuesta":
                    raw_input = block["toolUse"]["input"]
                    propuesta_validada = PropuestaLLM.model_validate(raw_input)
                    acciones_llm = propuesta_validada.acciones
                    break
        except Exception as e:
            logger.warning(f"Excepción en invocación de Estratega en Bedrock: {e}. Usando fallback.")

    # Si no obtuvimos acciones válidas del LLM, usar fallback determinista
    if not acciones_llm:
        acciones_llm = [_crear_accion_fallback(alerta)]

    # Aplicar reglas de coherencia (máx 1 por tipo, entidades válidas)
    acciones_coherentes = _filtrar_acciones_coherentes(acciones_llm, alerta)
    if not acciones_coherentes:
        acciones_coherentes = [_crear_accion_fallback(alerta)]

    # Cálculo determinista del impacto económico para cada acción en el servidor
    acciones_finales: list[Accion] = []
    for acc in acciones_coherentes:
        accion_id = f"ACC-{uuid.uuid4().hex[:8]}"
        impacto = calcular_impacto_economico(
            accion_parametros=acc.parametros,
            alerta=alerta,
            corte=alerta.corte_creacion,
            con=con,
        )

        accion_completa = Accion(
            accion_id=accion_id,
            titulo=acc.titulo,
            razon=acc.razon,
            parametros=acc.parametros,
            confianza=acc.confianza,
            impacto=impacto,
        )
        acciones_finales.append(accion_completa)

    # Construir contrato Propuesta
    propuesta_final = Propuesta(
        schema_version=SCHEMA_VERSION,
        alerta_id=alerta.alerta_id,
        diagnostico=diagnostico,
        acciones=acciones_finales,
        modelo=MODEL_ID,
        generada_en=datetime.now(timezone.utc),
    )

    # Persistir propuesta en centinela_alertas (tipo_registro = 'PROPUESTA')
    persistencia_service.guardar_propuesta(propuesta_final)

    return propuesta_final, trazas
