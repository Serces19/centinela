# evals/test_telemetry_emf.py
"""Pruebas unitarias de observabilidad, logging estructurado JSON y métricas CloudWatch EMF (Fase 3b).

Verifica:
1. Conformidad estricta con la especificación AWS CloudWatch Embedded Metric Format (EMF).
2. Estructura JSON: clave `_aws`, Namespace "Centinela", dimensiones, métricas y valores.
3. Sanitización de privacidad y PII: nunca filtra campos sensibles en logs ni métricas.
4. Emisión correcta de las 10 métricas clave requeridas por docs/05_monitorizacion.md:
   - AlertasGeneradas
   - PipelineLatenciaMs
   - LlmTokensEntrada / LlmTokensSalida / CostoUsdPorAlerta
   - ValidacionFallida
   - ReintentosLlm
   - SinEvidencia
   - GuardrailIntervino
   - BitacoraCadenaRota
   - AprobacionesHumanas / Rechazos
"""

import json
from services.telemetry import (
    ctx_alerta_id,
    ctx_request_id,
    emitir_alertas_generadas,
    emitir_bitacora_cadena_rota,
    emitir_decision_humana,
    emitir_guardrail_intervino,
    emitir_llm_tokens,
    emitir_metrica_emf,
    emitir_pipeline_latencia,
    emitir_reintentos_llm,
    emitir_sin_evidencia,
    emitir_validacion_fallida,
    log_evento,
    sanitizar_datos_log,
)


def test_emf_formato_especificacion_aws():
    """Valida que emitir_metrica_emf genere la estructura canónica requerida por AWS EMF."""
    res = emitir_metrica_emf(
        namespace="Centinela",
        dimensiones=[["Agente"]],
        metricas=[{"Name": "PipelineLatenciaMs", "Unit": "Milliseconds"}],
        valores={"Agente": "analista", "PipelineLatenciaMs": 420.5},
        propiedades={"evento": "test.pipeline"},
    )

    assert "_aws" in res
    aws_meta = res["_aws"]
    assert "Timestamp" in aws_meta
    assert isinstance(aws_meta["Timestamp"], int)
    assert aws_meta["Timestamp"] > 1_700_000_000_000  # Epoch en milisegundos

    metrics_def = aws_meta["CloudWatchMetrics"]
    assert len(metrics_def) == 1
    cw = metrics_def[0]
    assert cw["Namespace"] == "Centinela"
    assert cw["Dimensions"] == [["Agente"]]
    assert cw["Metrics"] == [{"Name": "PipelineLatenciaMs", "Unit": "Milliseconds"}]

    # Campos a nivel raíz
    assert res["Agente"] == "analista"
    assert res["PipelineLatenciaMs"] == 420.5
    assert res["evento"] == "test.pipeline"


def test_emf_alertas_generadas():
    """Valida métrica EMF AlertasGeneradas con dimensiones Kpi y Severidad."""
    res = emitir_alertas_generadas(kpi="margen", severidad="critica", count=1)
    assert res["Kpi"] == "margen"
    assert res["Severidad"] == "critica"
    assert res["AlertasGeneradas"] == 1
    assert res["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [["Kpi", "Severidad"]]


def test_emf_pipeline_latencia():
    """Valida métrica EMF PipelineLatenciaMs para cada agente."""
    res = emitir_pipeline_latencia(agente="vigia", latencia_ms=125.45)
    assert res["Agente"] == "vigia"
    assert res["PipelineLatenciaMs"] == 125.45
    assert res["_aws"]["CloudWatchMetrics"][0]["Metrics"][0]["Unit"] == "Milliseconds"


def test_emf_llm_tokens_y_costo():
    """Valida métricas EMF de consumo de tokens y costo USD."""
    res = emitir_llm_tokens(agente="analista", tokens_in=1500, tokens_out=300, costo_usd=0.003)
    assert res["Agente"] == "analista"
    assert res["LlmTokensEntrada"] == 1500
    assert res["LlmTokensSalida"] == 300
    assert res["CostoUsdPorAlerta"] == 0.003


def test_emf_validacion_fallida_y_reintentos():
    """Valida métricas EMF de robustez de contratos Pydantic."""
    res_val = emitir_validacion_fallida(agente="analista")
    assert res_val["ValidacionFallida"] == 1
    assert res_val["Agente"] == "analista"

    res_rei = emitir_reintentos_llm(agente="analista")
    assert res_rei["ReintentosLlm"] == 1
    assert res_rei["Agente"] == "analista"


def test_emf_sin_evidencia():
    """Valida métrica EMF SinEvidencia."""
    res = emitir_sin_evidencia(agente="analista")
    assert res["SinEvidencia"] == 1
    assert res["Agente"] == "analista"


def test_emf_guardrail_intervino():
    """Valida métrica EMF GuardrailIntervino para ataques y PII."""
    res_ataque = emitir_guardrail_intervino(tipo="ataque")
    assert res_ataque["Tipo"] == "ataque"
    assert res_ataque["GuardrailIntervino"] == 1

    res_pii = emitir_guardrail_intervino(tipo="pii")
    assert res_pii["Tipo"] == "pii"
    assert res_pii["GuardrailIntervino"] == 1


def test_emf_bitacora_cadena_rota():
    """Valida métrica EMF crítica BitacoraCadenaRota."""
    res = emitir_bitacora_cadena_rota(tipo="sha256_o_secuencia_invalida")
    assert res["BitacoraCadenaRota"] == 1
    assert res["Tipo"] == "sha256_o_secuencia_invalida"


def test_emf_decision_humana():
    """Valida métricas EMF de AprobacionesHumanas y Rechazos."""
    res_aprob = emitir_decision_humana(decision="aprobada")
    assert res_aprob["AprobacionesHumanas"] == 1
    assert res_aprob["Decision"] == "aprobada"

    res_rech = emitir_decision_humana(decision="rechazada")
    assert res_rech["Rechazos"] == 1
    assert res_rech["Decision"] == "rechazada"


def test_sanitizacion_pii_y_cifras_en_logs():
    """Valida que campos con PII y cifras de negocio queden estrictamente excluidos de los logs."""
    datos_crudos = {
        "nombre": "Carlos Gómez",
        "email": "carlos@andina.com",
        "telefono": "3001234567",
        "direccion": "Calle 45 # 12-34",
        "dinero_en_riesgo": 23558346,
        "saldo_cop": 8500000,
        "kpi": "margen",
        "entidad_id": "PR08",
        "estado": "nueva",
    }

    limpio = sanitizar_datos_log(datos_crudos)
    # Campos sensibles deben desaparecer
    assert "nombre" not in limpio
    assert "email" not in limpio
    assert "telefono" not in limpio
    assert "direccion" not in limpio
    assert "dinero_en_riesgo" not in limpio
    assert "saldo_cop" not in limpio

    # Metadatos operativos deben preservarse
    assert limpio["kpi"] == "margen"
    assert limpio["entidad_id"] == "PR08"
    assert limpio["estado"] == "nueva"


def test_log_evento_estructurado():
    """Valida la generación de logs JSON estructurados con trazabilidad de request_id y alerta_id."""
    token_req = ctx_request_id.set("req-test-999")
    token_alr = ctx_alerta_id.set("ALR-20260930-abc123")
    try:
        entrada = log_evento(
            nivel="INFO",
            evento="test.auditoria",
            agente="vigia",
            kpi="cartera",
            entidad_id="C0496",
            nombre_cliente="Supermercado El Sol",  # Debe filtrarse
        )
        assert entrada["request_id"] == "req-test-999"
        assert entrada["alerta_id"] == "ALR-20260930-abc123"
        assert entrada["agente"] == "vigia"
        assert entrada["evento"] == "test.auditoria"
        assert entrada["kpi"] == "cartera"
        assert entrada["entidad_id"] == "C0496"
        assert "nombre_cliente" not in entrada
    finally:
        ctx_request_id.reset(token_req)
        ctx_alerta_id.reset(token_alr)
