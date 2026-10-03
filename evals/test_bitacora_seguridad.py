# evals/test_bitacora_seguridad.py
"""Pruebas de seguridad e inmutabilidad criptográfica de la bitácora y control de decisiones:

- Inmutabilidad estricta: cualquier alteración de payload, hash, hash_prev o secuencia rompe la cadena.
- Detección de cadena rota con verificar_cadena().
- Idempotencia en decisiones humanas (DecisionRequest con misma Idempotency-Key).
- Bloqueo optimista (If-Match y conflicto de versión 409).
- Validación de transiciones de estado permitidas (solo desde 'propuesta').
- Reglas de validación de negocio: rechazo exige motivo obligatorio >= 10 caracteres.
- Endpoints de consulta y verificación de bitácora (/bitacora y /bitacora/{id}).
"""

from datetime import date, datetime, timezone
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from agents.graph import aplicar_decision_humana
from agents.vigia import generar_alertas
from api.main import app
from contracts.agentes import Accion, AjustePrecio, DiagnosticoLLM, ImpactoCalculado, Propuesta
from contracts.alertas import Alerta
from contracts.base import AlertaId, CERO_HASH, EstadoAlerta, Severidad
from contracts.bitacora import EntradaBitacora, Evento, verificar_cadena
from contracts.decision import DecisionRequest
from contracts.evidencia import CifraTrazable
from services.persistencia import persistencia_service


@pytest.fixture(autouse=True)
def setup_persistencia():
    """Asegura entorno de persistencia en memoria limpio para cada prueba."""
    persistencia_service.use_memory = True
    persistencia_service._mem_alertas.clear()
    persistencia_service._mem_bitacora.clear()
    persistencia_service._mem_trazas.clear()
    persistencia_service._mem_propuestas.clear()
    persistencia_service._mem_resultados.clear()
    persistencia_service._mem_feedback.clear()


@pytest.fixture
def alerta_en_propuesta() -> Alerta:
    """Crea una alerta lista en estado PROPUESTA con propuesta y eventos iniciales sellados."""
    alr_id = f"ALR-20260815-{uuid.uuid4().hex[:6]}"
    alertas = generar_alertas(date(2026, 8, 15))
    base = alertas[0].model_copy(update={"alerta_id": alr_id, "estado": EstadoAlerta.PROPUESTA})
    persistencia_service.guardar_alerta(base)

    # Sellar eventos de creación y propuesta
    persistencia_service.sellar_evento(
        alerta_id=alr_id,
        evento=Evento.ALERTA_CREADA,
        actor="vigia",
        payload={"huella": base.huella_causa, "riesgo": float(base.dinero_en_riesgo_cop)},
    )
    persistencia_service.sellar_evento(
        alerta_id=alr_id,
        evento=Evento.ANALISIS_COMPLETO,
        actor="analista",
        payload={"evidencia": True, "confianza": 0.9},
    )
    persistencia_service.sellar_evento(
        alerta_id=alr_id,
        evento=Evento.PROPUESTA_GENERADA,
        actor="estratega",
        payload={"num_acciones": 1},
    )

    diagnostico = DiagnosticoLLM(
        resumen="Alerta en estado de propuesta para evaluacion de auditoria",
        causa_raiz="Desviacion de costo unitario por encima del umbral de tolerancia",
        cifras=[CifraTrazable(etiqueta="Riesgo", valor=1000000.0, unidad="COP", consulta_id="Q-0123456789ab")],
        politicas=[],
        evidencia_suficiente=True,
        confianza=0.9,
    )
    accion = Accion(
        accion_id="ACC-01234567",
        titulo="Ajuste de precio",
        razon="Mitigacion de impacto de costo",
        parametros=AjustePrecio(skus=["P0001"], pct_ajuste=10.0),
        confianza=0.9,
        impacto=ImpactoCalculado(
            valor_cop=1000000,
            horizonte="mensual",
            metodo="delta_costo",
            consulta_ids=["Q-0123456789ab"],
        ),
    )
    propuesta = Propuesta(
        alerta_id=alr_id,
        diagnostico=diagnostico,
        acciones=[accion],
        generada_en=datetime.now(timezone.utc),
        modelo="haiku-4.5",
    )
    persistencia_service.guardar_propuesta(propuesta)
    return base


# =============================================================================
# Pruebas de Inmutabilidad Criptográfica de la Bitácora
# =============================================================================
def test_bitacora_cadena_valida(alerta_en_propuesta: Alerta):
    """Una cadena generada naturalmente pasa la verificación criptográfica al 100%."""
    entradas = persistencia_service.obtener_bitacora(alerta_en_propuesta.alerta_id)
    assert len(entradas) == 3
    assert verificar_cadena(entradas) is True
    assert entradas[0].hash_prev == CERO_HASH
    assert entradas[1].hash_prev == entradas[0].hash
    assert entradas[2].hash_prev == entradas[1].hash


def test_bitacora_falla_por_alteracion_payload(alerta_en_propuesta: Alerta):
    """Alterar un solo campo del payload de una entrada rompe la verificación SHA-256."""
    entradas = persistencia_service.obtener_bitacora(alerta_en_propuesta.alerta_id)
    assert verificar_cadena(entradas) is True

    # Manipulación maliciosa de un dato de auditoría
    payload_alterado = dict(entradas[1].payload)
    payload_alterado["confianza"] = 0.1
    corrupta = [entradas[0], entradas[1].model_copy(update={"payload": payload_alterado}), entradas[2]]

    assert verificar_cadena(corrupta) is False, "La alteración de payload debe romper la cadena"


def test_bitacora_falla_por_alteracion_hash(alerta_en_propuesta: Alerta):
    """Alterar deliberadamente el hash de una entrada rompe la verificación de enlace."""
    entradas = persistencia_service.obtener_bitacora(alerta_en_propuesta.alerta_id)
    assert verificar_cadena(entradas) is True

    # Modificar el hash sellado de la entrada 2
    corrupta = [entradas[0], entradas[1].model_copy(update={"hash": "0" * 64}), entradas[2]]

    assert verificar_cadena(corrupta) is False, "Un hash alterado debe romper la verificación"


def test_bitacora_falla_por_alteracion_secuencia(alerta_en_propuesta: Alerta):
    """Eliminar o alterar el número de secuencia (seq) rompe la verificación."""
    entradas = persistencia_service.obtener_bitacora(alerta_en_propuesta.alerta_id)
    assert verificar_cadena(entradas) is True

    # Alterar secuencia: saltarse un número
    corrupta = [entradas[0], entradas[1], entradas[2].model_copy(update={"seq": 99})]

    assert verificar_cadena(corrupta) is False, "Una secuencia alterada debe romper la verificación"


def test_bitacora_falla_por_omision_de_bloque_intermedio(alerta_en_propuesta: Alerta):
    """Omitir un bloque intermedio de la auditoría hace que hash_prev no coincida."""
    entradas = persistencia_service.obtener_bitacora(alerta_en_propuesta.alerta_id)
    assert len(entradas) == 3

    # Omitir el bloque intermedio (seq=2)
    cadena_mutilada = [entradas[0], entradas[2]]

    assert verificar_cadena(cadena_mutilada) is False, "Omitir un bloque debe romper la cadena"


# =============================================================================
# Pruebas de Idempotencia y Concurrencia en Decisiones
# =============================================================================
def test_idempotencia_decision_humana(alerta_en_propuesta: Alerta):
    """Repetir la misma decisión con la misma Idempotency-Key retorna el resultado sin duplicar."""
    client = TestClient(app)
    alr_id = alerta_en_propuesta.alerta_id
    version_inicial = alerta_en_propuesta.version

    payload_dec = {
        "decision": "aprobar",
        "accion_ids": ["ACC-01234567"],
        "decidido_por": "usuario:sergio.tester",
    }
    headers = {"Idempotency-Key": "idemp-test-100", "If-Match": str(version_inicial)}

    # Primera llamada
    resp1 = client.post(f"/alertas/{alr_id}/decision", json=payload_dec, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["alerta"]["estado"] == "ejecutada"

    total_bitacora_1 = len(persistencia_service.obtener_bitacora(alr_id))

    # Segunda llamada (reintento idéntico)
    resp2 = client.post(f"/alertas/{alr_id}/decision", json=payload_dec, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["alerta"]["estado"] == "ejecutada"

    # La bitácora no debe haber duplicado eventos
    total_bitacora_2 = len(persistencia_service.obtener_bitacora(alr_id))
    assert total_bitacora_2 == total_bitacora_1, "El reintento idempotente no debe duplicar eventos en la bitácora"


def test_conflicto_version_optimista_409(alerta_en_propuesta: Alerta):
    """Enviar un If-Match con versión obsoleta retorna 409 conflicto_version."""
    client = TestClient(app)
    alr_id = alerta_en_propuesta.alerta_id

    payload_dec = {
        "decision": "aprobar",
        "accion_ids": ["ACC-01234567"],
        "decidido_por": "usuario:sergio.tester",
    }
    headers = {"Idempotency-Key": "idemp-conflict-01", "If-Match": "999"}

    resp = client.post(f"/alertas/{alr_id}/decision", json=payload_dec, headers=headers)
    assert resp.status_code == 409
    data = resp.json()
    assert data["codigo"] == "conflicto_version"


def test_transicion_invalida_si_no_esta_en_propuesta():
    """No se permite tomar decisiones sobre alertas en estado 'nueva' o 'en_analisis'."""
    client = TestClient(app)
    alr_id = f"ALR-20260815-{uuid.uuid4().hex[:6]}"
    alertas = generar_alertas(date(2026, 8, 15))
    alerta_nueva = alertas[0].model_copy(update={"alerta_id": alr_id, "estado": EstadoAlerta.NUEVA})
    persistencia_service.guardar_alerta(alerta_nueva)

    payload_dec = {
        "decision": "aprobar",
        "accion_ids": ["ACC-01234567"],
        "decidido_por": "usuario:sergio.tester",
    }
    headers = {"Idempotency-Key": "idemp-invalid-trans"}

    resp = client.post(f"/alertas/{alr_id}/decision", json=payload_dec, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["codigo"] == "transicion_invalida"


def test_validacion_motivo_obligatorio_en_rechazo():
    """Rechazar exige motivo obligatorio de al menos 10 caracteres."""
    # Menos de 10 caracteres debe fallar en validación Pydantic de DecisionRequest
    with pytest.raises(Exception):
        DecisionRequest(
            decision="rechazar",
            accion_ids=[],
            motivo="corto",  # 5 caracteres < 10
            decidido_por="usuario:sergio.tester",
        )

    # Con 10 o más caracteres debe ser válido
    req_valido = DecisionRequest(
        decision="rechazar",
        accion_ids=[],
        motivo="Motivo de rechazo suficientemente largo y justificado",
        decidido_por="usuario:sergio.tester",
    )
    assert req_valido.decision == "rechazar"
    assert len(req_valido.motivo) >= 10


# =============================================================================
# Pruebas de Endpoints de Bitácora (/bitacora y /bitacora/{id})
# =============================================================================
def test_endpoint_bitacora_ambas_rutas(alerta_en_propuesta: Alerta):
    """Verifica que tanto /bitacora/{id} como /bitacora?alerta_id= funcionen con verificar=true."""
    client = TestClient(app)
    alr_id = alerta_en_propuesta.alerta_id

    # 1. Ruta /bitacora/{alerta_id}
    resp1 = client.get(f"/bitacora/{alr_id}?verificar=true")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["alerta_id"] == alr_id
    assert data1["total_entradas"] == 3
    assert data1["cadena_valida"] is True

    # 2. Ruta /bitacora?alerta_id= (Handshake H10)
    resp2 = client.get(f"/bitacora?alerta_id={alr_id}&verificar=true")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["alerta_id"] == alr_id
    assert data2["cadena_valida"] is True
    assert len(data2["entradas"]) == 3
