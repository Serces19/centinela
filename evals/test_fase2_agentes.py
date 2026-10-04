# evals/test_fase2_agentes.py
"""Pruebas de evaluación para Fases 2B, 2C y 2D:

- Agente Analista (Claude Haiku 4.5, Tool Use, Cifras Trazables, Sin Números Sueltos, Trazas LLM).
- Agente Estratega (Lista cerrada de acciones, Cálculo determinista de impacto, Coherencia de entidades).
- Orquestador LangGraph con Human-in-the-Loop (interrupt, MemorySaver/DynamoDB, reanudación y Ejecutor).
- Endpoints API (/alertas/{id}, /alertas/{id}/procesar, /alertas/{id}/decision con Idempotency-Key e If-Match).
"""

from datetime import date, datetime, timezone
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from agents.analista import analizar_alerta
from agents.estratega import _filtrar_acciones_coherentes, generar_propuesta
from agents.pipeline import aplicar_decision_humana, procesar_alerta_completa
from agents.vigia import generar_alertas
from api.main import app
from contracts.agentes import (
    AccionLLM,
    AjustePrecio,
    ContactoCartera,
    DiagnosticoLLM,
    Propuesta,
)
from contracts.alertas import Alerta
from contracts.base import AlertaId, EstadoAlerta
from contracts.bitacora import verificar_cadena
from contracts.decision import DecisionRequest
from contracts.evidencia import CifraTrazable, CitaPolitica, numeros_sueltos
from services.persistencia import persistencia_service


@pytest.fixture(autouse=True)
def setup_persistencia():
    """Asegura modo memoria para pruebas unitarias limpias y aisladas."""
    persistencia_service.use_memory = True
    persistencia_service._mem_alertas.clear()
    persistencia_service._mem_bitacora.clear()
    persistencia_service._mem_trazas.clear()
    persistencia_service._mem_propuestas.clear()
    persistencia_service._mem_resultados.clear()


@pytest.fixture
def alerta_s1():
    """Genera la alerta real de S1 (incremento de costo PR08) a corte 2026-08-15."""
    alertas = generar_alertas(date(2026, 8, 15))
    alerta = next((a for a in alertas if "PR08" in a.huella_causa), None)
    assert alerta is not None, "La alerta S1 (PR08) debe ser detectada a corte 2026-08-15"
    persistencia_service.guardar_alerta(alerta)
    return alerta


# =============================================================================
# Fase 2B: Pruebas del Agente Analista
# =============================================================================
@pytest.mark.asyncio
async def test_analista_diagnostico_s1(alerta_s1: Alerta):
    """Verifica que el Analista ejecute el bucle de razonamiento, devuelva un DiagnosticoLLM

    válido por Pydantic v2, cite OPE-POL-007, registre cifras trazables y genere TrazaLLM.
    """
    diagnostico, trazas = await analizar_alerta(alerta_s1)

    assert isinstance(diagnostico, DiagnosticoLLM)
    assert isinstance(diagnostico.resumen, str) and len(diagnostico.resumen) > 10
    assert isinstance(diagnostico.causa_raiz, str) and len(diagnostico.causa_raiz) > 10

    # Verificación de contrato: No números sueltos en resumen ni causa_raiz
    sueltos = numeros_sueltos(diagnostico.resumen + " " + diagnostico.causa_raiz)
    assert not sueltos, f"Se encontraron números sueltos en el texto del diagnóstico: {sueltos}"

    # Verificación de trazas y costo
    assert len(trazas) >= 1
    for t in trazas:
        assert t.agente == "analista"
        assert t.modelo is not None
        assert t.tokens_in >= 0
        assert t.tokens_out >= 0
        assert t.costo_usd >= 0.0

    # Trazas guardadas en persistencia
    trazas_guardadas = persistencia_service.obtener_trazas(alerta_s1.alerta_id)
    assert len(trazas_guardadas) >= 1


# =============================================================================
# Fase 2C: Pruebas del Agente Estratega y Coherencia
# =============================================================================
@pytest.mark.asyncio
async def test_estratega_propuesta_s1(alerta_s1: Alerta):
    """Verifica que el Estratega formule una Propuesta con acciones tipadas, sin montos

    en el LLM y con cálculo determinista de impacto en el servidor.
    """
    # Diagnóstico sintético riguroso para evaluar el Estratega de forma determinista
    diagnostico = DiagnosticoLLM(
        resumen="Incremento de costo en proveedor PR08 afecta cuatro productos de la linea Hogar",
        causa_raiz="El proveedor PR08 incremento costos unitarios por encima del umbral de politica OPE-POL-007",
        cifras=[
            CifraTrazable(etiqueta="Incremento de costo", valor=20.0, unidad="%", consulta_id="Q-0123456789ab"),
            CifraTrazable(etiqueta="Dinero en riesgo mensual", valor=23558346.0, unidad="COP", consulta_id="Q-0123456789ab"),
        ],
        politicas=[
            CitaPolitica(
                documento="OPE-POL-007",
                seccion="§4 Notificación de cambios de costo",
                fragmento_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            )
        ],
        supuestos=["Demanda se mantendrá constante"],
        evidencia_suficiente=True,
        confianza=0.9,
    )

    propuesta, trazas = await generar_propuesta(alerta_s1, diagnostico)

    assert isinstance(propuesta, Propuesta)
    assert propuesta.alerta_id == alerta_s1.alerta_id
    assert 1 <= len(propuesta.acciones) <= 3

    # Comprobar cálculo determinista de impacto
    for accion in propuesta.acciones:
        assert accion.accion_id.startswith("ACC-")
        assert accion.impacto is not None
        assert accion.impacto.valor_cop > 0
        assert accion.impacto.consulta_ids is not None

    # Verificar persistencia de la propuesta
    propuesta_obtenida = persistencia_service.obtener_propuesta(alerta_s1.alerta_id)
    assert propuesta_obtenida is not None
    assert propuesta_obtenida.alerta_id == alerta_s1.alerta_id


def test_coherencia_estratega_descarte_inventados(alerta_s1: Alerta):
    """Verifica que el filtro de coherencia descarte o ajuste acciones con entidades no existentes."""
    acciones_llm = [
        # Acción 1: SKU inventado que no está en la alerta
        AccionLLM(
            titulo="Ajuste de precio inválido",
            razon="Intento con SKU inventado",
            parametros=AjustePrecio(skus=["P9999"], pct_ajuste=12.0),
            confianza=0.8,
        ),
        # Acción 2: Contacto a cliente inventado
        AccionLLM(
            titulo="Contacto a cliente inventado",
            razon="Intento con cliente no existente en S1",
            parametros=ContactoCartera(cliente_id="C9999", nivel="llamada_acuerdo"),
            confianza=0.8,
        ),
    ]

    acciones_coherentes = _filtrar_acciones_coherentes(acciones_llm, alerta_s1)
    assert len(acciones_coherentes) >= 1
    # Verifica que el SKU P9999 fue corregido con los SKUs reales de la alerta S1
    for a in acciones_coherentes:
        if isinstance(a.parametros, AjustePrecio):
            assert "P9999" not in a.parametros.skus
            assert any(s in ("P0005", "P0006", "P0007", "P0008") for s in a.parametros.skus)


# =============================================================================
# Fase 2D: Endpoints HTTP de FastAPI (/alertas, /alertas/{id}, /procesar, /decision)
# =============================================================================
def test_api_procesar_y_decision_flujo_completo(alerta_s1: Alerta):
    """Prueba integral de los endpoints FastAPI:

    - GET /alertas/{id}
    - POST /alertas/{id}/procesar
    - POST /alertas/{id}/decision (con Idempotency-Key e If-Match)
    - Manejo de errores 400 y 409
    """
    client = TestClient(app)
    alerta_id = alerta_s1.alerta_id

    # 1. GET /alertas/{id}
    resp_get = client.get(f"/alertas/{alerta_id}")
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["alerta"]["alerta_id"] == alerta_id
    assert "ETag" in resp_get.headers
    etag_version = resp_get.headers["ETag"].strip('"')

    # 2. POST /alertas/{id}/procesar (dispara analista y estratega)
    resp_proc = client.post(f"/alertas/{alerta_id}/procesar")
    assert resp_proc.status_code == 200
    data_proc = resp_proc.json()
    assert data_proc["alerta"]["estado"] == "propuesta"
    assert data_proc["propuesta"] is not None
    acciones = data_proc["propuesta"]["acciones"]
    assert len(acciones) >= 1
    accion_ids = [a["accion_id"] for a in acciones]

    version_actual = data_proc["alerta"]["version"]

    # 3. Decision: Error 400 si falta Idempotency-Key
    resp_sin_key = client.post(
        f"/alertas/{alerta_id}/decision",
        json={"decision": "aprobar", "accion_ids": accion_ids, "decidido_por": "usuario:sergio"},
    )
    assert resp_sin_key.status_code == 400

    # 4. Decision: Error 409 si If-Match tiene versión obsoleta
    resp_conflict = client.post(
        f"/alertas/{alerta_id}/decision",
        headers={"Idempotency-Key": "idemp-001", "If-Match": "999"},
        json={"decision": "aprobar", "accion_ids": accion_ids, "decidido_por": "usuario:sergio"},
    )
    assert resp_conflict.status_code == 409
    assert resp_conflict.json()["codigo"] == "conflicto_version"

    # 5. Decision: Aprobación exitosa con Idempotency-Key e If-Match correcto
    resp_dec = client.post(
        f"/alertas/{alerta_id}/decision",
        headers={"Idempotency-Key": "idemp-002", "If-Match": str(version_actual)},
        json={"decision": "aprobar", "accion_ids": accion_ids, "decidido_por": "usuario:sergio"},
    )
    assert resp_dec.status_code == 200
    data_dec = resp_dec.json()
    assert data_dec["alerta"]["estado"] == "ejecutada"
    assert data_dec["resultado"]["ok"] is True
    assert len(data_dec["resultado"]["borradores"]) == len(accion_ids)

    # 6. Idempotencia: enviar la misma decisión nuevamente retorna el resultado exitoso
    resp_idemp = client.post(
        f"/alertas/{alerta_id}/decision",
        headers={"Idempotency-Key": "idemp-002"},
        json={"decision": "aprobar", "accion_ids": accion_ids, "decidido_por": "usuario:sergio"},
    )
    assert resp_idemp.status_code == 200
    assert resp_idemp.json()["alerta"]["estado"] == "ejecutada"

    # 7. Validar cadena inmutable de bitácora sellada
    resp_bit = client.get(f"/bitacora/{alerta_id}?verificar=true")
    assert resp_bit.status_code == 200
    bit_data = resp_bit.json()
    assert bit_data["cadena_valida"] is True
    assert bit_data["total_entradas"] >= 4
