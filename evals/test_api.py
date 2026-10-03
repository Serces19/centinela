# evals/test_api.py
"""Pruebas unitarias e integrales para la API FastAPI de Centinela.

Cubre:
- Healthcheck (GET /health)
- Streaming SSE (GET /stream)
- Reloj de simulación (GET /simulacion/corte, POST /simulacion/avanzar, POST /simulacion/reiniciar)
- Generación y consulta de alertas con nombres resueltos (GET /alertas -> AlertaVista)
- Consulta de bitácora y verificación criptográfica (GET /bitacora/{alerta_id})
- Idempotencia de persistencia de alertas
"""

from datetime import date
import json
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.contracts.alertas import AlertaVista
from backend.contracts.configuracion import CORTE_INICIAL_LIMPIO, FECHA_CORTE_DEFECTO
from backend.contracts.operacion import SimulacionResp
from backend.services.persistencia import PersistenciaService, persistencia_service


@pytest.fixture
def client():
    # Usar modo memoria durante pruebas de API para rapidez e independencia de red
    persistencia_service.use_memory = True
    persistencia_service.reiniciar_reloj()
    persistencia_service._mem_alertas.clear()
    persistencia_service._mem_bitacora.clear()
    with TestClient(app) as c:
        yield c


def test_health(client):
    """GET /health debe responder 200 con status ok y metadatos del servicio."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["servicio"] == "centinela"
    assert "x-request-id" in resp.headers


def test_stream_sse(client):
    """GET /stream debe emitir 5 eventos SSE en tiempo real."""
    with client.stream("GET", "/stream") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        
        events = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                payload = json.loads(line.replace("data: ", ""))
                events.append(payload)

    assert len(events) == 5
    for i, ev in enumerate(events, start=1):
        assert ev["evento"] == "token"
        assert f"{i}/5" in ev["texto"]


def test_simulacion_reloj_flujo(client):
    """Prueba el ciclo completo de consulta, avance y reinicio del reloj."""
    # 1. Consulta corte inicial
    resp = client.get("/simulacion/corte")
    assert resp.status_code == 200
    data = resp.json()
    assert data["corte"] == CORTE_INICIAL_LIMPIO.isoformat()
    assert data["corte_inicial_limpio"] == CORTE_INICIAL_LIMPIO.isoformat()
    assert data["corte_maximo"] == FECHA_CORTE_DEFECTO.isoformat()

    # 2. Avanzar 10 días
    resp_adv = client.post("/simulacion/avanzar?dias=10")
    assert resp_adv.status_code == 200
    sim_data = resp_adv.json()
    esperado = date(2026, 6, 28).isoformat()
    assert sim_data["corte"] == esperado
    assert sim_data["dias_avanzados"] == 10
    assert sim_data["pipeline_disparado"] is True

    # 3. Validar nuevo corte
    resp2 = client.get("/simulacion/corte")
    assert resp2.json()["corte"] == esperado

    # 4. Rechazar avance más allá del límite
    resp_excess = client.post("/simulacion/avanzar?dias=200")
    assert resp_excess.status_code == 400
    assert "supera la fecha maxima" in resp_excess.json()["detail"]

    # 5. Reiniciar simulacion
    resp_reset = client.post("/simulacion/reiniciar")
    assert resp_reset.status_code == 200
    assert resp_reset.json()["corte"] == CORTE_INICIAL_LIMPIO.isoformat()

    # 6. Validar que volvió al inicio
    resp_final = client.get("/simulacion/corte")
    assert resp_final.json()["corte"] == CORTE_INICIAL_LIMPIO.isoformat()


def test_listar_alertas_alerta_vista(client):
    """GET /alertas debe devolver alertas tipadas como AlertaVista con nombres resueltos."""
    # Probar con corte 2026-09-30 (donde se manifiestan los escenarios S1-S6)
    resp = client.get("/alertas?corte=2026-09-30&persistir=true")
    assert resp.status_code == 200
    alertas_data = resp.json()
    assert len(alertas_data) > 0

    # Validar que cada objeto deserializa como AlertaVista
    vistas = [AlertaVista.model_validate(item) for item in alertas_data]
    assert len(vistas) == len(alertas_data)

    # Validar que se resolvieron nombres legibles de entidades
    todas_resoluciones = {}
    for v in vistas:
        todas_resoluciones.update(v.nombres_resueltos)
        assert v.alerta.alerta_id.startswith("ALR-20260930-")
        assert v.alerta.dinero_en_riesgo_cop >= 0

    # Asegurar que se resolvieron nombres para entidades clave de los escenarios
    assert "PR08" in todas_resoluciones or "C0496" in todas_resoluciones or "V03" in todas_resoluciones
    if "PR08" in todas_resoluciones:
        assert isinstance(todas_resoluciones["PR08"], str) and len(todas_resoluciones["PR08"]) > 0


def test_bitacora_y_cadena_criptografica(client):
    """Verifica que las alertas persistidas crean entradas en la bitácora con hash válido."""
    # Persistir alertas para corte 2026-08-15 (detecta S1)
    resp = client.get("/alertas?corte=2026-08-15&persistir=true")
    assert resp.status_code == 200
    alertas = resp.json()
    assert len(alertas) > 0

    primera_alerta_id = alertas[0]["alerta"]["alerta_id"]

    # Consultar bitácora con verificación criptográfica
    resp_bit = client.get(f"/bitacora/{primera_alerta_id}?verificar=true")
    assert resp_bit.status_code == 200
    bit_data = resp_bit.json()

    assert bit_data["alerta_id"] == primera_alerta_id
    assert bit_data["total_entradas"] >= 1
    assert bit_data["cadena_valida"] is True
    assert bit_data["entradas"][0]["evento"] == "alerta_creada"
    assert bit_data["entradas"][0]["actor"] == "vigia"


def test_idempotencia_persistencia_alertas(client):
    """Reejecutar el Vigía con el mismo corte no duplica alertas ni bitácora."""
    # Primera persistencia
    resp1 = client.get("/alertas?corte=2026-08-15&persistir=true")
    assert resp1.status_code == 200
    count1 = len(resp1.json())
    alerta_id = resp1.json()[0]["alerta"]["alerta_id"]

    bit1 = client.get(f"/bitacora/{alerta_id}").json()
    assert bit1["total_entradas"] == 1

    # Segunda persistencia con el mismo corte
    resp2 = client.get("/alertas?corte=2026-08-15&persistir=true")
    assert resp2.status_code == 200
    assert len(resp2.json()) == count1

    bit2 = client.get(f"/bitacora/{alerta_id}").json()
    # No se debe haber agregado una segunda entrada 'alerta_creada' idéntica
    assert bit2["total_entradas"] == 1
