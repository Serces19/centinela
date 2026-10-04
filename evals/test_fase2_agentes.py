# evals/test_fase2_agentes.py
"""Analista, Estratega y flujo de decisión (R7).

- Ficha de evidencia: cifras reales con consulta registrada.
- Playbook: parámetros de las acciones por regla de política (no por el modelo).
- Analista y Estratega con Claude Haiku 4.5 real: texto sin números propios, cifras citadas con marcadores.
- Aprendizaje: un rechazo previo cambia la propuesta siguiente.
- API: procesar -> decisión (Idempotency-Key, If-Match) -> ejecutada -> bitácora verificada.
"""

from datetime import date
import re

import pytest
from fastapi.testclient import TestClient

from agents.analista import analizar_alerta
from agents.estratega import generar_propuesta
from agents.evidencia import construir_ficha
from agents.playbook import generar_candidatas
from agents.vigia import generar_alertas
from api.main import app
from contracts.agentes import DiagnosticoLLM, Propuesta
from contracts.base import EstadoAlerta
from contracts.evidencia import numeros_sueltos, referencias_cifras, renderizar_texto
from services.persistencia import persistencia_service
from services.registro_consultas import consulta_en_cache
from services.umbrales import Umbrales


@pytest.fixture(autouse=True)
def memoria_limpia():
    persistencia_service.borrar_estado_demo()
    persistencia_service._mem_bitacora.clear()


def _alerta(corte: date, huella: str):
    alerta = next(a for a in generar_alertas(corte) if a.huella_causa == huella)
    persistencia_service.persistir_alertas_nuevas([alerta])
    return alerta


# ---------------------------------------------------------------------------
# Evidencia y playbook (deterministas)
# ---------------------------------------------------------------------------
def test_ficha_s1_cifras_reales_y_consulta_registrada():
    corte = date(2026, 8, 15)
    ficha = construir_ficha(_alerta(corte, "costo|PR08"), corte)
    por_etiqueta = {c.etiqueta: c for c in ficha.cifras}
    assert por_etiqueta["Alza de costo del proveedor (máxima entre los SKU)"].valor == 25.0
    assert por_etiqueta["SKU del proveedor con alza de costo"].valor == 4
    assert por_etiqueta["Margen mínimo de la línea (política)"].valor == 25.0
    assert por_etiqueta["Margen más bajo entre los SKU al precio de lista"].valor == pytest.approx(5.8, abs=0.05)
    for c in ficha.cifras:   # toda cifra apunta a una consulta registrada y reproducible
        q = consulta_en_cache(c.consulta_id)
        assert q is not None and q.filas > 0 and "DATE '2026-08-15'" in q.sql_renderizado


def test_playbook_aplica_la_politica():
    u = Umbrales()
    c09 = date(2026, 9, 30)
    casos = {
        "saldo_vencido|C0496": ["solo_contado", "llamada_acuerdo"],      # 34 días vencido: solo contado (FIN-POL-004 §4)
        "descuento_en_exceso|V03": ["suspender_facultad_cotizar", "revision_previa_cotizacion"],
        "cobertura_dias|P0119": ["contactar_proveedor", "entrega_parcial", "proveedor_alterno"],
        "veces_intervalo_habitual|C0061": ["visita", "llamada", "oferta"],
    }
    for huella, esperado in casos.items():
        alerta = _alerta(c09, huella)
        cands = generar_candidatas(alerta, construir_ficha(alerta, c09), u)
        p = [getattr(c.parametros, "nivel", None) or getattr(c.parametros, "medida", None) or getattr(c.parametros, "via", None) or getattr(c.parametros, "canal", None) for c in cands]
        assert p == esperado, huella
    s6 = _alerta(c09, "venta_bajo_costo|P0097")
    assert [c.parametros.tipo for c in generar_candidatas(s6, construir_ficha(s6, c09), u)] == ["corregir_venta_bajo_costo"]


def test_playbook_ajuste_de_precio_repone_el_margen_minimo():
    corte = date(2026, 8, 15)
    alerta = _alerta(corte, "costo|PR08")
    ficha = construir_ficha(alerta, corte)
    cands = generar_candidatas(alerta, ficha, Umbrales())
    assert [c.parametros.tipo for c in cands] == ["ajuste_precio", "renegociar_proveedor"]
    ajuste = cands[0].parametros
    assert 0 < ajuste.pct_ajuste <= 30 and set(ajuste.skus) == {"P0001", "P0006", "P0011", "P0021"}
    # con ese ajuste, el SKU ponderado más pesado alcanza el margen mínimo de la línea
    filas = {f["sku"]: f for f in ficha.contexto["skus"]}
    sku = max(filas.values(), key=lambda f: f["unidades_30d"] * f["precio_lista"])
    nuevo_margen = 1 - sku["costo_unitario"] / (sku["precio_lista"] * (1 + ajuste.pct_ajuste / 100))
    assert nuevo_margen * 100 >= sku["margen_minimo_pct"] - 8     # ajuste ponderado: no iguala SKU por SKU


# ---------------------------------------------------------------------------
# Analista y Estratega con el modelo real
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analista_s1_explica_con_cifras_trazables():
    corte = date(2026, 8, 15)
    alerta = _alerta(corte, "costo|PR08")
    diag, trazas = await analizar_alerta(alerta)

    assert isinstance(diag, DiagnosticoLLM) and diag.evidencia_suficiente and diag.confianza >= 0.6
    texto = diag.resumen + " " + diag.causa_raiz
    assert referencias_cifras(texto), "el texto debe citar cifras con marcadores {cN}"
    assert numeros_sueltos(texto, diag.numeros_politica) == []
    rendido = renderizar_texto(texto, diag.cifras)
    assert "{c" not in rendido and "25 %" in rendido
    assert any(c.documento == "OPE-POL-007" for c in diag.politicas)
    assert len(diag.cifras) >= 5 and all(consulta_en_cache(c.consulta_id) for c in diag.cifras)
    if trazas and trazas[-1].tokens_in:
        assert sum(t.costo_usd for t in trazas) > 0


@pytest.mark.asyncio
async def test_estratega_s1_elige_entre_candidatas_y_calcula_impacto():
    corte = date(2026, 8, 15)
    alerta = _alerta(corte, "costo|PR08")
    diag, _ = await analizar_alerta(alerta)
    propuesta, _ = await generar_propuesta(alerta, diag)

    assert isinstance(propuesta, Propuesta) and 1 <= len(propuesta.acciones) <= 3
    ficha = construir_ficha(alerta, corte)
    candidatas = {c.parametros.tipo: c.parametros for c in generar_candidatas(alerta, ficha, Umbrales())}
    for a in propuesta.acciones:
        assert a.parametros == candidatas[a.parametros.tipo], "el modelo no puede cambiar los parámetros de la candidata"
        assert a.impacto.valor_cop > 0 and a.impacto.consulta_ids and a.impacto.descripcion
        texto = a.titulo + " " + a.razon
        assert numeros_sueltos(texto) == []
        assert all(1 <= i <= len(propuesta.cifras) for i in referencias_cifras(texto))
    assert len({a.parametros.tipo for a in propuesta.acciones}) == len(propuesta.acciones)


@pytest.mark.asyncio
async def test_un_rechazo_previo_cambia_la_propuesta_siguiente():
    corte = date(2026, 8, 15)
    alerta = _alerta(corte, "costo|PR08")
    diag, _ = await analizar_alerta(alerta)
    persistencia_service.guardar_feedback(
        alerta_id="ALR-20260701-aaaaaa", motivo="El proveedor ya aceptó revertir el alza, no subir precios",
        actor="usuario:pruebas", huella_causa="costo|PR99", familia="costo", tipos_accion=["ajuste_precio"],
    )
    propuesta, _ = await generar_propuesta(alerta, diag)
    assert propuesta.acciones[0].parametros.tipo == "renegociar_proveedor"
    tipos = [a.parametros.tipo for a in propuesta.acciones]
    assert "ajuste_precio" not in tipos[:1]
    assert propuesta.aprendizaje and "revertir el alza" in propuesta.aprendizaje[0]


# ---------------------------------------------------------------------------
# API: procesar -> decisión -> bitácora
# ---------------------------------------------------------------------------
def test_api_procesar_decision_y_reabrir():
    client = TestClient(app)
    client.post("/simulacion/reiniciar")
    client.post("/simulacion/avanzar?dias=58")            # 2026-08-15
    s1 = next(v for v in client.get("/alertas").json() if v["alerta"]["huella_causa"] == "costo|PR08")
    alerta_id = s1["alerta"]["alerta_id"]

    proc = client.post(f"/alertas/{alerta_id}/procesar")
    assert proc.status_code == 200
    data = proc.json()
    assert data["alerta"]["estado"] == "propuesta" and data["alerta"]["paso_actual"] == "ninguno"
    assert data["propuesta"]["acciones"] and data["propuesta"]["cifras"]
    accion_ids = [a["accion_id"] for a in data["propuesta"]["acciones"]]
    version = data["alerta"]["version"]

    assert client.post(f"/alertas/{alerta_id}/decision", json={"decision": "aprobar", "accion_ids": accion_ids, "decidido_por": "usuario:sergio"}).status_code == 400
    conflicto = client.post(f"/alertas/{alerta_id}/decision", headers={"Idempotency-Key": "k1", "If-Match": "999"},
                            json={"decision": "aprobar", "accion_ids": accion_ids, "decidido_por": "usuario:sergio"})
    assert conflicto.status_code == 409 and conflicto.json()["codigo"] == "conflicto_version"

    # Rechazar con motivo y reabrir: Centinela vuelve a proponer teniendo en cuenta el rechazo
    rechazo = client.post(f"/alertas/{alerta_id}/decision", headers={"Idempotency-Key": "k2", "If-Match": str(version)},
                          json={"decision": "rechazar", "motivo": "Comercial prefiere renegociar antes de tocar precios.", "decidido_por": "usuario:sergio"})
    assert rechazo.status_code == 200 and rechazo.json()["alerta"]["estado"] == "rechazada"
    assert client.post(f"/alertas/{alerta_id}/reabrir?actor=usuario:sergio").json()["alerta"]["estado"] == "nueva"
    segunda = client.post(f"/alertas/{alerta_id}/procesar").json()
    assert segunda["alerta"]["estado"] == "propuesta"
    assert segunda["propuesta"]["aprendizaje"], "la nueva propuesta debe explicar qué aprendió del rechazo"
    nuevos_ids = [a["accion_id"] for a in segunda["propuesta"]["acciones"]]

    aprobada = client.post(f"/alertas/{alerta_id}/decision", headers={"Idempotency-Key": "k3"},
                           json={"decision": "aprobar", "accion_ids": nuevos_ids, "decidido_por": "usuario:sergio"})
    assert aprobada.status_code == 200 and aprobada.json()["alerta"]["estado"] == EstadoAlerta.EJECUTADA.value
    assert len(aprobada.json()["resultado"]["borradores"]) == len(nuevos_ids)
    assert all(b["destino"].startswith("sandbox://") for b in aprobada.json()["resultado"]["borradores"])

    # Idempotencia y bitácora encadenada
    assert client.post(f"/alertas/{alerta_id}/decision", headers={"Idempotency-Key": "k3"},
                       json={"decision": "aprobar", "accion_ids": nuevos_ids, "decidido_por": "usuario:sergio"}).status_code == 200
    bit = client.get(f"/bitacora?alerta_id={alerta_id}&verificar=true").json()
    assert bit["cadena_valida"] is True and bit["total_entradas"] >= 8
    assert {e["evento"] for e in bit["entradas"]} >= {"alerta_creada", "analisis_completo", "propuesta_generada", "decision_humana", "alerta_reabierta", "accion_ejecutada"}
