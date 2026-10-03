"""Pruebas unitarias para la herramienta `calcular_impacto` determinista."""

from datetime import date
import pytest

from contracts.herramientas import CalcularImpactoIn
from tools.impacto import calcular_impacto


def test_impacto_s1_costo_proveedor():
    """S1: Incremento de costo de proveedor PR08 a corte 2026-08-15 reproduce ≈ $23.55M COP."""
    inp = CalcularImpactoIn(
        metodo="delta_costo_x_unidades_30d",
        parametros={"proveedor_id": "PR08"},
    )
    res = calcular_impacto(inp, corte=date(2026, 8, 15))
    assert res.horizonte == "mensual"
    assert abs(res.valor_cop - 23558346) / 23558346 < 0.01
    assert res.intervalo_cop is not None


def test_impacto_s4_exceso_descuento():
    """S4: Suma de exceso de descuento para V03 al 2026-09-30 es $8.096.844 COP."""
    inp = CalcularImpactoIn(
        metodo="exceso_descuento",
        parametros={"vendedor_id": "V03"},
    )
    res = calcular_impacto(inp, corte=date(2026, 9, 30))
    assert res.horizonte == "unico"
    assert abs(res.valor_cop - 8096844) <= 1


def test_impacto_s2_cartera_vencida():
    """S2: Cartera vencida de cliente C0496 al 2026-09-30 es $48.647.744 COP."""
    inp = CalcularImpactoIn(
        metodo="cartera_vencida_en_riesgo",
        parametros={"cliente_id": "C0496"},
    )
    res = calcular_impacto(inp, corte=date(2026, 9, 30))
    assert res.horizonte == "unico"
    assert res.valor_cop == 48647744
    assert res.intervalo_cop == (48647744, 89461493)


def test_impacto_s6_venta_bajo_costo():
    """S6: Pérdida directa por ventas bajo costo al 2026-09-30 es $2.721.412 COP."""
    inp = CalcularImpactoIn(
        metodo="margen_perdido_bajo_costo",
        parametros={},
    )
    res = calcular_impacto(inp, corte=date(2026, 9, 30))
    assert res.horizonte == "unico"
    assert res.valor_cop == 2721412


def test_impacto_s5_cliente_inactivo():
    """S5: Ventas promedio mensuales de cliente inactivo C0061."""
    inp = CalcularImpactoIn(
        metodo="ventas_perdidas_cliente_inactivo",
        parametros={"cliente_id": "C0061"},
    )
    res = calcular_impacto(inp, corte=date(2026, 9, 30))
    assert res.horizonte == "mensual"
    assert res.valor_cop == 29469987
    assert res.intervalo_cop is not None


def test_impacto_s3_quiebre_inventario():
    """S3: Ventas perdidas por quiebre para P0119 en BOD-MDE."""
    inp = CalcularImpactoIn(
        metodo="ventas_perdidas_quiebre",
        parametros={"sku": "P0119", "bodega_id": "BOD-MDE"},
    )
    res = calcular_impacto(inp, corte=date(2026, 9, 30))
    assert res.horizonte == "unico"
    assert res.valor_cop > 0
    assert len(res.consulta_ids) >= 1
