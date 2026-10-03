"""Evaluación EJ-01: Verificación de cifras SQL de los escenarios y consultas tipo jurado.

Comprueba determinismo y exactitud contra las 7 vistas de la capa semántica en DuckDB.
"""

from datetime import date
from decimal import Decimal
import pytest
from semantic.db import get_duckdb_connection


def test_escenario_s4_descuentos_en_exceso():
    """S4: Vendedor V03 tiene 316 líneas con descuento fuera de política y $8.096.844 en exceso al 2026-09-30."""
    con = get_duckdb_connection(date(2026, 9, 30))
    res = con.execute("""
        SELECT count(*), round(sum(descuento_en_exceso))
        FROM v_descuentos_fuera_politica
        WHERE vendedor_id = 'V03'
    """).fetchone()

    lineas, monto_total = res
    assert lineas == 316
    assert abs(monto_total - 8096844.0) <= 1.0


def test_escenario_s5_cliente_que_se_va():
    """S5: Cliente C0061 compró por última vez el 2026-07-09 tras 43 pedidos no cancelados."""
    con = get_duckdb_connection(date(2026, 9, 30))
    res = con.execute("""
        SELECT pedidos, ultima_compra, veces_intervalo_habitual
        FROM v_actividad_cliente
        WHERE cliente_id = 'C0061'
    """).fetchone()

    pedidos, ultima_compra, veces_intervalo = res
    assert pedidos == 43
    assert ultima_compra == date(2026, 7, 9)
    assert veces_intervalo >= 3.0  # Umbral de política (> 3x)


def test_escenario_s6_venta_bajo_costo():
    """S6: 116 líneas de pedido vendidas por debajo del costo unitario con pérdida de $2.721.412."""
    con = get_duckdb_connection(date(2026, 9, 30))
    res = con.execute("""
        SELECT count(*), round(sum(costo_total - valor_neto))
        FROM v_ventas
        WHERE valor_neto < costo_total
    """).fetchone()

    lineas, perdida_total = res
    assert lineas == 116
    assert perdida_total == Decimal("2721412")


def test_escenario_s1_incremento_costo_impacto():
    """S1: Alza de costo de proveedor PR08 en 4 SKU el 2026-08-15 genera impacto mensual ≈ $23.55 M COP."""
    con = get_duckdb_connection(date(2026, 8, 15))
    res = con.execute("""
        WITH deltas AS (
            SELECT 'P0001' AS sku, 7710 AS delta
            UNION ALL SELECT 'P0006', 2544
            UNION ALL SELECT 'P0011', 3912
            UNION ALL SELECT 'P0021', 4224
        ),
        dem_30d AS (
            SELECT sku, sum(salidas) AS unidades_30d
            FROM inventario_diario
            WHERE fecha > DATE '2026-07-15' AND fecha < DATE '2026-08-15'
            GROUP BY sku
        )
        SELECT round(sum(d.unidades_30d * s.delta))
        FROM deltas s
        JOIN dem_30d d USING (sku)
    """).fetchone()

    impacto = float(res[0])
    # Verifica que el impacto mensual está en el rango esperado (≈ $23.55 M COP)
    assert abs(impacto - 23558346) / 23558346 < 0.01  # tolerancia menor al 1%


def test_pregunta_jurado_1_margen_linea_mes():
    """Pregunta Jurado 1: ¿Cuál fue el margen de la línea Hogar en septiembre de 2026?"""
    con = get_duckdb_connection(date(2026, 9, 30))
    res = con.execute("""
        SELECT round(100.0 * (1.0 - sum(costo_total) / sum(valor_neto)), 2)
        FROM v_ventas
        WHERE linea = 'Hogar'
          AND date_trunc('month', fecha)::date = '2026-09-01'
    """).fetchone()

    margen_pct = res[0]
    assert margen_pct == 22.3  # Cayó por debajo del mínimo de política (25%)


def test_pregunta_jurado_2_saldo_vencido_cliente():
    """Pregunta Jurado 2: ¿Cuál es el saldo vencido y mora máxima de C0496 a corte 2026-09-30?"""
    con = get_duckdb_connection(date(2026, 9, 30))
    res = con.execute("""
        SELECT saldo_vencido, max_dias_vencido
        FROM v_cartera_cliente
        WHERE cliente_id = 'C0496'
    """).fetchone()

    saldo_vencido, dias_vencido = res
    assert saldo_vencido == Decimal("48647744.00")
    assert dias_vencido == 34


def test_pregunta_jurado_3_cobertura_sku_bodega():
    """Pregunta Jurado 3: ¿Cuál es la cobertura y pedidos pendientes de P0119 en BOD-MDE a corte 2026-09-30?"""
    con = get_duckdb_connection(date(2026, 9, 30))
    res = con.execute("""
        SELECT cobertura_dias, unidades_pendientes
        FROM v_cobertura_inventario
        WHERE sku = 'P0119' AND bodega_id = 'BOD-MDE'
    """).fetchone()

    cobertura_dias, pendientes = res
    assert cobertura_dias == 3.5  # Crítico (< 5 días clase A)
    assert pendientes == 85
