"""Módulo de conexión a DuckDB y montaje de capa semántica en memoria."""

from datetime import date
from pathlib import Path
import duckdb

_SEMANTIC_DIR = Path(__file__).resolve().parent
_DB_PATH = _SEMANTIC_DIR / "centinela.duckdb"
_VIEWS_SQL_PATH = _SEMANTIC_DIR / "views.sql"

FECHA_CORTE_DEFECTO = date(2026, 9, 30)


def get_duckdb_connection(corte: date | None = None, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """Abre conexión a centinela.duckdb y carga las 7 vistas temporales parametrizadas por `corte`."""
    if not _DB_PATH.exists():
        raise FileNotFoundError(f"Base de datos no encontrada en {_DB_PATH}. Ejecutar scripts/build_duckdb.py")

    fecha = corte or FECHA_CORTE_DEFECTO
    con = duckdb.connect(str(_DB_PATH), read_only=read_only)
    con.execute("USE centinela;")

    # Macro de fecha de corte para la sesión
    con.execute(f"CREATE OR REPLACE TEMP MACRO fecha_corte() AS DATE '{fecha.isoformat()}';")

    # Carga de las 7 vistas temporales
    views_sql = _VIEWS_SQL_PATH.read_text(encoding="utf-8")
    con.execute(views_sql)

    return con
