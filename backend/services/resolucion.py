# backend/services/resolucion.py
"""Servicio determinista de resolución de nombres de entidades para la UI (PII segregation)."""

from typing import Iterable
from semantic.db import get_duckdb_connection


def resolver_nombres(ids: Iterable[str]) -> dict[str, str]:
    """Resuelve nombres legibles de clientes, proveedores, vendedores, productos y bodegas.

    Garantiza que la UI muestre nombres legibles mientras que los agentes y herramientas
    operan exclusivamente sobre IDs deterministas.
    """
    id_list = list(set(ids))
    if not id_list:
        return {}

    nombres: dict[str, str] = {}
    con = get_duckdb_connection()
    try:
        for ident in id_list:
            if not ident:
                continue
            # Vendedores: V01..V99
            if ident.startswith("V") and len(ident) <= 4 and ident[1:].isdigit():
                res = con.execute("SELECT nombre FROM vendedores WHERE vendedor_id = ?", [ident]).fetchone()
                if res and res[0]:
                    nombres[ident] = str(res[0])
            # Clientes: C0001..C9999
            elif ident.startswith("C") and len(ident) <= 6 and ident[1:].isdigit():
                res = con.execute("SELECT nombre FROM clientes WHERE cliente_id = ?", [ident]).fetchone()
                if res and res[0]:
                    nombres[ident] = str(res[0])
            # Proveedores: PR01..PR99
            elif ident.startswith("PR") and len(ident) <= 5 and ident[2:].isdigit():
                res = con.execute("SELECT nombre FROM proveedores WHERE proveedor_id = ?", [ident]).fetchone()
                if res and res[0]:
                    nombres[ident] = str(res[0])
            # Productos / SKU: P0001..P9999
            elif ident.startswith("P") and len(ident) <= 6 and ident[1:].isdigit():
                res = con.execute("SELECT nombre FROM productos WHERE sku = ?", [ident]).fetchone()
                if res and res[0]:
                    nombres[ident] = str(res[0])
            # Bodegas: BOD-XXX
            elif ident.startswith("BOD-"):
                res = con.execute("SELECT nombre FROM bodegas WHERE bodega_id = ?", [ident]).fetchone()
                if res and res[0]:
                    nombres[ident] = str(res[0])
    finally:
        con.close()

    return nombres
