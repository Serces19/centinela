"""Impacto económico determinista de cada tipo de acción (consultas registradas, sin respaldos inventados)."""

from datetime import date

import pytest

from agents.vigia import generar_alertas
from contracts.agentes import (
    AjustePrecio,
    ContactoCartera,
    CorregirVentaBajoCosto,
    ExpeditarOC,
    ReactivarCliente,
    RenegociarProveedor,
    RevisionDescuentos,
)
from tools.impacto import calcular_impacto_economico


def _alerta(corte: date, huella: str):
    return next(a for a in generar_alertas(corte) if a.huella_causa == huella)


def test_renegociar_proveedor_reproduce_sobrecosto_s1():
    corte = date(2026, 8, 15)
    alerta = _alerta(corte, "costo|PR08")
    res = calcular_impacto_economico(
        RenegociarProveedor(proveedor_id="PR08", skus=["P0001", "P0006", "P0011", "P0021"]), alerta, corte
    )
    assert res.horizonte == "mensual"
    assert abs(res.valor_cop - 23_522_184) / 23_522_184 < 0.01
    assert res.consulta_ids and res.descripcion


def test_ajuste_de_precio_recupera_menos_que_el_sobrecosto():
    corte = date(2026, 8, 15)
    alerta = _alerta(corte, "costo|PR08")
    sobrecosto = calcular_impacto_economico(
        RenegociarProveedor(proveedor_id="PR08", skus=["P0001", "P0006", "P0011", "P0021"]), alerta, corte
    ).valor_cop
    ajuste = calcular_impacto_economico(AjustePrecio(skus=["P0001", "P0006", "P0011", "P0021"], pct_ajuste=10.0), alerta, corte)
    assert 0 < ajuste.valor_cop < sobrecosto * 1.5
    assert ajuste.intervalo_cop is not None and ajuste.intervalo_cop[1] == ajuste.valor_cop


def test_exceso_descuento_s4():
    corte = date(2026, 9, 30)
    res = calcular_impacto_economico(RevisionDescuentos(vendedor_id="V03", medida="revision_previa_cotizacion"), _alerta(corte, "descuento_en_exceso|V03"), corte)
    assert res.horizonte == "unico" and abs(res.valor_cop - 8_096_844) <= 1


def test_cartera_vencida_s2():
    corte = date(2026, 9, 30)
    res = calcular_impacto_economico(ContactoCartera(cliente_id="C0496", nivel="solo_contado"), _alerta(corte, "saldo_vencido|C0496"), corte)
    assert res.valor_cop == 48_647_744 and res.intervalo_cop == (48_647_744, 89_461_493)


def test_cliente_inactivo_s5():
    corte = date(2026, 9, 30)
    res = calcular_impacto_economico(ReactivarCliente(cliente_id="C0061", vendedor_id="V18", canal="visita"), _alerta(corte, "veces_intervalo_habitual|C0061"), corte)
    assert res.horizonte == "mensual" and res.valor_cop == 29_469_987


def test_quiebre_s3():
    corte = date(2026, 9, 30)
    res = calcular_impacto_economico(
        ExpeditarOC(oc_id="OC-003421", proveedor_id="PR23", sku="P0119", bodega_id="BOD-MDE", via="contactar_proveedor"),
        _alerta(corte, "cobertura_dias|P0119"), corte,
    )
    assert res.horizonte == "unico" and res.valor_cop > 0


def test_venta_bajo_costo_por_sku():
    corte = date(2026, 9, 30)
    res = calcular_impacto_economico(CorregirVentaBajoCosto(skus=["P0097"]), _alerta(corte, "venta_bajo_costo|P0097"), corte)
    assert res.valor_cop == 1_476_747


def test_sin_datos_el_impacto_es_cero_y_no_se_rellena_con_el_riesgo_de_la_alerta():
    corte = date(2026, 9, 30)
    alerta = _alerta(corte, "saldo_vencido|C0496")
    res = calcular_impacto_economico(ContactoCartera(cliente_id="C9999", nivel="recordatorio"), alerta, corte)
    assert res.valor_cop == 0 and alerta.dinero_en_riesgo_cop > 0
