# backend/tools/consultas.py
"""Herramienta FastMCP `consultar_vista` con validador estricto de SQL.

Garantiza:
- Solo vistas autorizadas en la lista blanca (`v_*`).
- Solo columnas autorizadas por vista.
- Sin sentencias arbitrarias, sin subconsultas, sin comentarios ni inyecciones.
- Límite forzado <= 500 filas.
- Generación de `ConsultaRegistrada` con hash SHA-256 canónico del resultado.
"""

from datetime import date
import re
from typing import Any

import duckdb
from fastmcp import FastMCP

from contracts.base import Vista
from contracts.herramientas import ConsultarVistaIn, ConsultarVistaOut, Filtro
from semantic.db import FECHA_CORTE_DEFECTO, get_duckdb_connection
from services.registro_consultas import registrar_resultado, renderizar_sql, serializar_valor

# Servidor FastMCP in-process
mcp = FastMCP("centinela-tools")

# Columnas permitidas por vista (estrictamente de la definición de capa semántica)
COLUMNAS_PERMITIDAS: dict[str, set[str]] = {
    Vista.VENTAS.value: {
        "pedido_id", "fecha", "cliente_id", "cliente", "segmento", "vendedor_id",
        "ciudad", "region", "linea_n", "sku", "producto", "linea", "proveedor_id", "cantidad",
        "precio_lista", "precio_unitario", "descuento_pct", "aprobacion_especial",
        "valor_neto", "costo_total", "margen_bruto", "estado",
    },
    Vista.MARGEN_SEMANAL.value: {
        "semana", "linea", "ventas", "costo", "margen_pct",
    },
    Vista.CARTERA.value: {
        "cliente_id", "nombre", "segmento", "cupo_credito", "plazo_dias",
        "saldo_abierto", "saldo_vencido", "max_dias_vencido", "dias_pago_prom_120d",
    },
    Vista.DIAS_PAGO.value: {
        "cliente_id", "mes_factura", "dias_pago_prom", "facturas_pagadas",
    },
    Vista.COBERTURA.value: {
        "sku", "nombre", "linea", "proveedor_id", "clase_abc", "bodega_id", "existencia",
        "demanda_prom_30d", "cobertura_dias", "unidades_pendientes",
    },
    Vista.DESCUENTOS.value: {
        "pedido_id", "fecha", "cliente_id", "cliente", "segmento", "vendedor_id",
        "ciudad", "region", "linea_n", "sku", "producto", "linea", "proveedor_id", "cantidad",
        "precio_lista", "precio_unitario", "descuento_pct", "aprobacion_especial",
        "valor_neto", "costo_total", "margen_bruto", "estado",
        "tope_descuento_pct", "descuento_en_exceso",
    },
    Vista.ACTIVIDAD.value: {
        "cliente_id", "pedidos", "ultima_compra", "intervalo_prom_dias",
        "dias_sin_comprar", "veces_intervalo_habitual",
    },
}

_RE_INYECCION = re.compile(
    r"(;|--|/\*|\*/|\b(select|union|insert|update|delete|drop|alter|create|attach|detach|pragma|copy|load|exec|call)\b|"
    r"\b(pedidos|clientes|vendedores|proveedores|productos|bodegas|lista_precios|costos_proveedor|"
    r"ordenes_compra|pedidos_detalle|facturas|pagos|inventario_diario|ref_topes_descuento|"
    r"ref_margen_minimo_linea|ref_ciudad_bodega)\b)",
    re.IGNORECASE,
)

_RE_AGG = re.compile(r"^(sum|avg|min|max|count)\((distinct\s+)?([a-z_]+|\*)\)$", re.IGNORECASE)
_RE_AGG_ALIAS = re.compile(r"^(sum|avg|min|max|count)\((distinct\s+)?([a-z_]+|\*)\)\s+as\s+([a-z_]{1,40})$", re.IGNORECASE)


class ValidadorConsultaError(ValueError):
    """Error emitido cuando una consulta no cumple las reglas de validación estricta."""
    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.codigo = "validacion"
        self.mensaje = mensaje


def _validar_expresion_columna(col: str, permitidas: set[str]) -> str:
    """Valida que una columna o agregación simple pertenezca a la lista blanca."""
    col_limpia = col.strip()
    expresion = re.split(r"\s+as\s+", col_limpia, maxsplit=1, flags=re.IGNORECASE)[0]   # el alias se valida por patrón
    if _RE_INYECCION.search(expresion):
        raise ValidadorConsultaError(f"Intento de inyección o uso de tabla cruda detectado en columna: '{col}'")

    # Caso 1: Columna directa
    if col_limpia in permitidas:
        return col_limpia

    # Caso 2: Agregación simple agg(col)
    m = _RE_AGG.match(col_limpia)
    if m:
        agg, distinto, inner = m.group(1).lower(), "distinct " if m.group(2) else "", m.group(3)
        if inner == "*" and agg == "count" and not distinto:
            return "count(*)"
        if inner in permitidas:
            return f"{agg}({distinto}{inner})"

    # Caso 3: Agregación con alias agg(col) AS alias
    m_alias = _RE_AGG_ALIAS.match(col_limpia)
    if m_alias:
        agg, distinto, inner, alias = m_alias.group(1).lower(), "distinct " if m_alias.group(2) else "", m_alias.group(3), m_alias.group(4).lower()
        if inner == "*" and agg == "count" and not distinto:
            return f"count(*) AS {alias}"
        if inner in permitidas:
            return f"{agg}({distinto}{inner}) AS {alias}"

    raise ValidadorConsultaError(
        f"Columna o expresión '{col}' no permitida para esta vista. Columnas permitidas: {sorted(permitidas)}"
    )


def _validar_ordenar_por(ordenar_por: str, permitidas: set[str], alias: set[str] | None = None) -> str:
    """Valida la cláusula ORDER BY: columna permitida o alias definido en las columnas, y dirección ASC/DESC."""
    alias = alias or set()
    partes = ordenar_por.strip().split()
    if len(partes) == 1:
        col, direccion = partes[0], "ASC"
    elif len(partes) == 2 and partes[1].upper() in {"ASC", "DESC"}:
        col, direccion = partes[0], partes[1].upper()
    else:
        raise ValidadorConsultaError(f"Cláusula ordenar_por inválida: '{ordenar_por}'")

    if col.lower() in alias:
        return f"{col.lower()} {direccion}"
    if _RE_INYECCION.search(ordenar_por):
        raise ValidadorConsultaError(f"Intento de inyección detectado en ordenar_por: '{ordenar_por}'")
    if col not in permitidas:
        raise ValidadorConsultaError(f"Columna '{col}' en ordenar_por no permitida. Usa una columna de la vista o un alias definido en `columnas`.")
    return f"{col} {direccion}"


def consultar_vista(
    params: ConsultarVistaIn,
    corte: date | None = None,
    con: Any = None,
    descripcion: str = "",
) -> ConsultarVistaOut:
    """Ejecuta una consulta validada contra la capa semántica de Centinela.

    Args:
        params: Configuración validada de la consulta (ConsultarVistaIn).
        corte: Fecha de corte simulada. Si es None se usa la fecha por defecto.
        con: Conexión DuckDB opcional reutilizable.
    """
    vista_val = params.vista.value if hasattr(params.vista, "value") else str(params.vista)
    if vista_val not in COLUMNAS_PERMITIDAS:
        raise ValidadorConsultaError(f"Vista '{vista_val}' no autorizada. Solo se permiten vistas v_*.")

    permitidas = COLUMNAS_PERMITIDAS[vista_val]

    # Validar límite estricto
    if params.limite < 1 or params.limite > 500:
        raise ValidadorConsultaError(f"Límite {params.limite} fuera de rango permitido (1-500).")

    # Validar columnas
    columnas_sql = [_validar_expresion_columna(c, permitidas) for c in params.columnas]

    # Validar filtros
    where_parts: list[str] = []
    sql_params: list[Any] = []

    for f in params.filtros:
        if f.columna not in permitidas:
            raise ValidadorConsultaError(
                f"Filtro sobre columna '{f.columna}' no permitida en vista {vista_val}."
            )
        if _RE_INYECCION.search(f.columna):
            raise ValidadorConsultaError(f"Intento de inyección en columna de filtro: '{f.columna}'")

        if f.op == "in":
            if not isinstance(f.valor, (list, tuple)) or len(f.valor) == 0:
                raise ValidadorConsultaError("El operador 'in' requiere una lista no vacía de valores.")
            placeholders = ", ".join(["?"] * len(f.valor))
            where_parts.append(f"{f.columna} IN ({placeholders})")
            for item in f.valor:
                if isinstance(item, str) and _RE_INYECCION.search(item):
                    raise ValidadorConsultaError("Inyección detectada en valor de filtro.")
                sql_params.append(item)
        else:
            if isinstance(f.valor, (list, tuple)):
                raise ValidadorConsultaError(f"Operador '{f.op}' no acepta listas como valor.")
            if isinstance(f.valor, str) and _RE_INYECCION.search(f.valor):
                raise ValidadorConsultaError("Inyección detectada en valor de filtro.")
            where_parts.append(f"{f.columna} {f.op} ?")
            sql_params.append(f.valor)

    # Validar agrupar_por
    for g in params.agrupar_por:
        if g not in permitidas:
            raise ValidadorConsultaError(f"Columna de agrupación '{g}' no permitida en {vista_val}.")
        if _RE_INYECCION.search(g):
            raise ValidadorConsultaError(f"Intento de inyección en agrupar_por: '{g}'")

    # Validar ordenar_por
    clausula_order = ""
    if params.ordenar_por:
        alias = {m.group(4).lower() for c in params.columnas if (m := _RE_AGG_ALIAS.match(c.strip()))}
        orden_seguro = _validar_ordenar_por(params.ordenar_por, permitidas, alias)
        clausula_order = f" ORDER BY {orden_seguro}"

    # Construir query SQL parametrizada
    sql = f"SELECT {', '.join(columnas_sql)} FROM {vista_val}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if params.agrupar_por:
        sql += " GROUP BY " + ", ".join(params.agrupar_por)
    sql += clausula_order
    sql += f" LIMIT {params.limite}"

    fecha_corte_efectiva = corte or FECHA_CORTE_DEFECTO

    # Ejecutar en DuckDB
    cerrar_con = False
    if con is None:
        con = get_duckdb_connection(fecha_corte_efectiva)
        cerrar_con = True

    try:
        cursor = con.execute(sql, sql_params)
        col_names = [desc[0] for desc in cursor.description]
        raw_rows = cursor.fetchall()
    finally:
        if cerrar_con:
            con.close()

    filas_serializadas: list[list[str | int | float | None]] = [
        [serializar_valor(val) for val in row] for row in raw_rows
    ]

    resultado = registrar_resultado(
        vista=vista_val,
        sql_renderizado=renderizar_sql(sql, sql_params),
        corte=fecha_corte_efectiva,
        columnas=col_names,
        filas=filas_serializadas,
        descripcion=descripcion,
    )

    return ConsultarVistaOut(
        consulta=resultado.consulta,
        columnas=col_names,
        filas=filas_serializadas,
        truncado=len(filas_serializadas) >= params.limite,
    )


@mcp.tool(name="consultar_vista")
def mcp_consultar_vista(params: ConsultarVistaIn, corte: date | None = None) -> ConsultarVistaOut:
    """Ejecuta una consulta validada contra la capa semántica de Centinela."""
    return consultar_vista(params, corte=corte)


# Alias explícito para interoperabilidad con agentes
ejecutar_consulta_vista = consultar_vista

