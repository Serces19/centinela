# backend/services/registro_consultas.py
"""Registro de consultas: toda cifra del sistema nace de una consulta registrada y reproducible.

- `consulta_id` determinista: `Q-` + sha256(SQL renderizado + corte)[:12].
- Cada ejecución produce una `ConsultaRegistrada` con SQL, corte, columnas, filas (hasta 300) y hash del resultado.
- Las consultas recientes se guardan en una caché acotada del proceso; la persistencia las escribe en
  DynamoDB (`centinela_trazas`) cuando una alerta referencia su `consulta_id`.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any

from contracts.evidencia import ConsultaRegistrada

FILAS_MAX = 300
_CACHE_MAX = 600
_CACHE: "OrderedDict[str, ConsultaRegistrada]" = OrderedDict()


@dataclass(frozen=True)
class ResultadoConsulta:
    consulta: ConsultaRegistrada
    columnas: list[str]
    filas: list[list[str | int | float | None]]


def serializar_valor(val: Any) -> str | int | float | None:
    """Convierte tipos de DuckDB a tipos serializables en contratos."""
    if val is None:
        return None
    if isinstance(val, (int, float, str)):
        return val
    if isinstance(val, Decimal):
        return int(val) if val % 1 == 0 else float(val)
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return str(val)


def renderizar_sql(sql_base: str, params: list[Any] | None) -> str:
    """SQL con los parámetros sustituidos, solo para trazabilidad (la ejecución usa parámetros)."""
    sql = sql_base
    for p in params or []:
        if isinstance(p, (int, float)):
            rep = str(p)
        elif isinstance(p, str):
            rep = "'" + p.replace("'", "''") + "'"
        elif isinstance(p, (date, datetime)):
            rep = f"DATE '{p.isoformat()}'"
        else:
            rep = repr(p)
        sql = sql.replace("?", rep, 1)
    return sql


def _normalizar_sql(sql: str) -> str:
    return " ".join(sql.split())


def registrar_resultado(
    *,
    vista: str,
    sql_renderizado: str,
    corte: date,
    columnas: list[str],
    filas: list[list[str | int | float | None]],
    descripcion: str = "",
    truncar: bool = True,
) -> ResultadoConsulta:
    """Construye y guarda en caché la `ConsultaRegistrada` de un resultado ya obtenido."""
    sql_norm = _normalizar_sql(sql_renderizado).replace("fecha_corte()", f"DATE '{corte.isoformat()}'")
    consulta_id = "Q-" + hashlib.sha256(f"{sql_norm}|{corte.isoformat()}".encode("utf-8")).hexdigest()[:12]
    canon = json.dumps([columnas, filas], sort_keys=True, ensure_ascii=False)
    resultado_hash = hashlib.sha256(canon.encode("utf-8")).hexdigest()

    consulta = ConsultaRegistrada(
        consulta_id=consulta_id,
        vista=vista,
        descripcion=descripcion[:200],
        sql_renderizado=sql_norm,
        corte=corte,
        filas=len(filas),
        columnas=columnas,
        filas_muestra=filas[:FILAS_MAX] if truncar else filas,
        resultado_hash=resultado_hash,
        ejecutada_en=datetime.now(timezone.utc),
    )
    _CACHE[consulta_id] = consulta
    _CACHE.move_to_end(consulta_id)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    try:
        from services.persistencia import persistencia_service
        persistencia_service.guardar_consulta(consulta)
    except Exception:
        pass
    return ResultadoConsulta(consulta=consulta, columnas=columnas, filas=filas)


def ejecutar_registrada(
    con: Any,
    sql: str,
    params: list[Any] | None = None,
    *,
    vista: str,
    corte: date,
    descripcion: str = "",
) -> ResultadoConsulta:
    """Ejecuta `sql` en la conexión DuckDB y registra la consulta con su resultado."""
    cursor = con.execute(sql, params or [])
    columnas = [d[0] for d in cursor.description]
    filas = [[serializar_valor(v) for v in fila] for fila in cursor.fetchall()]
    return registrar_resultado(
        vista=vista,
        sql_renderizado=renderizar_sql(sql, params),
        corte=corte,
        columnas=columnas,
        filas=filas,
        descripcion=descripcion,
    )


def consulta_en_cache(consulta_id: str) -> ConsultaRegistrada | None:
    return _CACHE.get(consulta_id)
