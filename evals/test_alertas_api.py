"""R3/R4/R6: una alerta por causa, resumen sin doble conteo, consultas registradas, reloj y configuración.

Usa la API real con persistencia en memoria (conftest). No invoca a Bedrock.
"""

from collections import Counter
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.contracts.configuracion import CORTE_INICIAL_LIMPIO


@pytest.fixture()
def client():
    with TestClient(app) as c:
        c.post("/simulacion/reiniciar")
        c.put("/config", json={"umbrales": {"dias_mora": 15}, "actor": "usuario:pruebas"})
        yield c
        c.post("/simulacion/reiniciar")


def _ir_a(client: TestClient, destino: date) -> dict:
    dias = (destino - CORTE_INICIAL_LIMPIO).days
    resp = client.post(f"/simulacion/avanzar?dias={dias}")
    assert resp.status_code == 200
    return resp.json()


def test_una_alerta_por_causa_y_ids_estables(client):
    _ir_a(client, date(2026, 8, 15))
    a1 = client.get("/alertas").json()
    huellas = [v["alerta"]["huella_causa"] for v in a1]
    assert len(huellas) == len(set(huellas)), "hay causas duplicadas"
    ids_agosto = {v["alerta"]["huella_causa"]: v["alerta"]["alerta_id"] for v in a1}
    assert "costo|PR08" in ids_agosto

    # Al avanzar al cierre, la misma causa conserva su alerta (id, estado) y aparecen las demás
    resp = client.post("/simulacion/avanzar?dias=46")
    assert resp.json()["alertas_nuevas"] >= 1
    a2 = client.get("/alertas").json()
    huellas2 = [v["alerta"]["huella_causa"] for v in a2]
    assert len(huellas2) == len(set(huellas2))
    for huella, alerta_id in ids_agosto.items():
        previa = next((v for v in a2 if v["alerta"]["huella_causa"] == huella), None)
        if previa:
            assert previa["alerta"]["alerta_id"] == alerta_id
    esperadas = {"costo|PR08", "saldo_vencido|C0496", "veces_intervalo_habitual|C0061", "descuento_en_exceso|V03", "cobertura_dias|P0119"}
    assert esperadas <= set(huellas2)


def test_resumen_sin_doble_conteo_y_decisiones_clave(client):
    _ir_a(client, date(2026, 9, 30))
    resumen = client.get("/alertas/resumen").json()
    alertas = client.get("/alertas").json()
    pendientes = [v["alerta"] for v in alertas if v["alerta"]["estado"] in ("nueva", "en_analisis", "propuesta")]
    assert resumen["pendientes"] == len(pendientes)
    assert resumen["total_dinero_en_riesgo_cop"] == sum(a["dinero_en_riesgo_cop"] for a in pendientes)
    clave = resumen["decisiones_clave"]
    assert 1 <= len(clave) <= 3
    familias = [v["alerta"]["huella_causa"].split("|")[0] for v in clave]
    assert len(familias) == len(set(familias)), "las decisiones clave deben ser de causas distintas"
    montos = [v["alerta"]["dinero_en_riesgo_cop"] for v in clave]
    assert montos == sorted(montos, reverse=True)


def test_consulta_registrada_enlazada_a_cada_hallazgo(client):
    _ir_a(client, date(2026, 8, 15))
    s1 = next(v for v in client.get("/alertas").json() if v["alerta"]["huella_causa"] == "costo|PR08")
    cid = s1["alerta"]["hallazgos"][0]["consulta_ids"][0]
    resp = client.get(f"/consultas/{cid}")
    assert resp.status_code == 200
    consulta = resp.json()
    assert consulta["consulta_id"] == cid
    assert "DATE '2026-08-15'" in consulta["sql_renderizado"]
    assert consulta["filas"] == len(consulta["filas_muestra"]) > 0
    assert len(consulta["resultado_hash"]) == 64
    assert any(fila[consulta["columnas"].index("proveedor_id")] == "PR08" for fila in consulta["filas_muestra"])
    assert client.get("/consultas/Q-000000000000").status_code == 404


def test_avanzar_reporta_alertas_y_reiniciar_limpia(client):
    r = _ir_a(client, date(2026, 8, 15))
    assert r["alertas_detectadas"] > 0 and r["alertas_nuevas"] > 0
    assert client.post("/simulacion/reiniciar").json()["corte"] == CORTE_INICIAL_LIMPIO.isoformat()
    # tras reiniciar no queda estado persistido: al detectar de nuevo vuelven a ser nuevas
    r2 = _ir_a(client, date(2026, 8, 15))
    assert r2["alertas_nuevas"] == r["alertas_nuevas"]


def test_configuracion_cambia_las_alertas_y_valida(client):
    _ir_a(client, date(2026, 9, 30))
    base = client.get("/config").json()
    assert {u["nombre"] for u in base["umbrales"]} >= {"dias_mora", "costo_alza_pct", "intervalo_veces"}
    assert all(u["valor"] == u["defecto"] for u in base["umbrales"])
    assert base["autonomia"]["ajuste_precio"] == "propone"

    antes = Counter(v["alerta"]["huella_causa"].split("|")[0] for v in client.get("/alertas?corte=2026-09-30").json())
    resp = client.put("/config", json={"umbrales": {"intervalo_veces": 6}, "actor": "usuario:pruebas"})
    assert resp.status_code == 200
    despues = Counter(v["alerta"]["huella_causa"].split("|")[0] for v in client.get("/alertas?corte=2026-09-30").json())
    assert despues["veces_intervalo_habitual"] < antes["veces_intervalo_habitual"]
    assert despues["veces_intervalo_habitual"] >= 1   # el cliente que se va sigue detectándose

    assert client.put("/config", json={"umbrales": {"dias_mora": 9999}, "actor": "usuario:pruebas"}).status_code == 422
    assert client.put("/config", json={"umbrales": {"no_existe": 1}, "actor": "usuario:pruebas"}).status_code == 422
    assert client.put("/config", json={"autonomia": {"ajuste_precio": "ejecuta"}, "actor": "usuario:pruebas"}).json()["autonomia"]["ajuste_precio"] == "ejecuta"
    client.put("/config", json={"umbrales": {"intervalo_veces": 3}, "autonomia": {"ajuste_precio": "propone"}, "actor": "usuario:pruebas"})


def test_bitacora_general_con_filtros(client):
    _ir_a(client, date(2026, 8, 15))
    general = client.get("/bitacora?limite=500").json()
    assert general["total_entradas"] > 0 and general["alerta_id"] is None
    assert all(e["actor"] == "vigia" for e in client.get("/bitacora?actor=vigia").json()["entradas"])
    una = general["entradas"][0]["alerta_id"]
    detalle = client.get(f"/bitacora?alerta_id={una}&verificar=true").json()
    assert detalle["cadena_valida"] is True
