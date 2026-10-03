"""Pruebas unitarias para la herramienta FastMCP `consultar_vista`.

Verifica:
- Consultas válidas sobre varias vistas de la capa semántica.
- Exactitud en columnas devueltas y tipos serializados.
- Rechazo estricto ante intentos de inyección SQL, tablas crudas y columnas no autorizadas.
- Cumplimiento de límites y validez de la trazabilidad (ConsultaRegistrada, hash SHA-256).
"""

from datetime import date
import pytest
from pydantic import ValidationError

from contracts.base import Vista
from contracts.herramientas import ConsultarVistaIn, Filtro
from tools.consultas import ValidadorConsultaError, consultar_vista


def test_consulta_valida_cartera_cliente():
    """Consulta válida sobre v_cartera_cliente con filtros y límite."""
    inp = ConsultarVistaIn(
        vista=Vista.CARTERA,
        columnas=["cliente_id", "nombre", "saldo_vencido", "max_dias_vencido"],
        filtros=[
            Filtro(columna="max_dias_vencido", op=">", valor=15),
            Filtro(columna="cliente_id", op="=", valor="C0496"),
        ],
        ordenar_por="saldo_vencido DESC",
        limite=10,
    )
    corte = date(2026, 9, 30)
    out = consultar_vista(inp, corte=corte)

    assert out.columnas == ["cliente_id", "nombre", "saldo_vencido", "max_dias_vencido"]
    assert len(out.filas) == 1
    fila = out.filas[0]
    assert fila[0] == "C0496"
    assert fila[2] == 48647744.0 or fila[2] == 48647744
    assert fila[3] == 34
    assert not out.truncado

    # Validar ConsultaRegistrada
    assert out.consulta.consulta_id.startswith("Q-")
    assert len(out.consulta.consulta_id) == 14  # Q- + 12 hex
    assert len(out.consulta.resultado_hash) == 64
    assert out.consulta.filas == 1
    assert out.consulta.vista == Vista.CARTERA


def test_consulta_valida_descuentos_fuera_politica():
    """Consulta válida sobre v_descuentos_fuera_politica para el vendedor V03."""
    inp = ConsultarVistaIn(
        vista=Vista.DESCUENTOS,
        columnas=["vendedor_id", "descuento_en_exceso", "descuento_pct"],
        filtros=[Filtro(columna="vendedor_id", op="=", valor="V03")],
        limite=100,
    )
    out = consultar_vista(inp, corte=date(2026, 9, 30))

    assert len(out.filas) == 100
    assert out.truncado is True  # Hay 316 líneas, por tanto se trunca a 100
    assert out.columnas == ["vendedor_id", "descuento_en_exceso", "descuento_pct"]


def test_consulta_valida_agregaciones_y_agrupacion():
    """Verifica agregaciones simples autorizadas como sum(...) y agrupar_por."""
    inp = ConsultarVistaIn(
        vista=Vista.MARGEN_SEMANAL,
        columnas=["linea", "sum(ventas) AS ventas_totales"],
        agrupar_por=["linea"],
        ordenar_por="linea ASC",
        limite=20,
    )
    out = consultar_vista(inp, corte=date(2026, 9, 30))
    assert len(out.filas) == 7  # 7 líneas de negocio
    lineas = [r[0] for r in out.filas]
    assert "Hogar" in lineas
    assert "Alimentos" in lineas


def test_rechazo_columna_inexistente():
    """Rechaza columnas que no están en la lista blanca de la vista."""
    inp = ConsultarVistaIn(
        vista=Vista.CARTERA,
        columnas=["cliente_id", "columna_fantasma"],
        limite=10,
    )
    with pytest.raises(ValidadorConsultaError) as exc_info:
        consultar_vista(inp, corte=date(2026, 9, 30))
    assert "no permitida" in str(exc_info.value)
    assert exc_info.value.codigo == "validacion"


def test_rechazo_inyeccion_sql_semicolon():
    """Rechaza intentos de inyección con punto y coma."""
    inp = ConsultarVistaIn(
        vista=Vista.VENTAS,
        columnas=["pedido_id; DROP TABLE pedidos;"],
        limite=10,
    )
    with pytest.raises(ValidadorConsultaError) as exc_info:
        consultar_vista(inp, corte=date(2026, 9, 30))
    assert exc_info.value.codigo == "validacion"



def test_rechazo_inyeccion_subconsulta_select():
    """Rechaza subconsultas SELECT en filtros o columnas."""
    with pytest.raises(ValidadorConsultaError):
        # El contrato permite la cadena en Filtro.columna si cumple el regex,
        # pero el validador estricto debe rechazarla.
        inp = ConsultarVistaIn(
            vista=Vista.VENTAS,
            columnas=["pedido_id"],
            filtros=[Filtro(columna="sku", op="=", valor="SELECT * FROM pedidos")],
            limite=10,
        )
        consultar_vista(inp, corte=date(2026, 9, 30))


def test_rechazo_tablas_crudas_en_ordenar_por():
    """Rechaza referencias a tablas crudas fuera de lista blanca en ordenar_por."""
    inp = ConsultarVistaIn(
        vista=Vista.VENTAS,
        columnas=["pedido_id"],
        ordenar_por="pedido_id; (SELECT count(*) FROM pedidos)",
        limite=10,
    )
    with pytest.raises(ValidadorConsultaError):
        consultar_vista(inp, corte=date(2026, 9, 30))


def test_rechazo_limite_invalido():
    """Valida que Pydantic o el validador rechacen límites mayores a 500 o menores a 1."""
    with pytest.raises(ValidationError):
        ConsultarVistaIn(
            vista=Vista.VENTAS,
            columnas=["pedido_id"],
            limite=501,
        )

    with pytest.raises(ValidationError):
        ConsultarVistaIn(
            vista=Vista.VENTAS,
            columnas=["pedido_id"],
            limite=0,
        )
