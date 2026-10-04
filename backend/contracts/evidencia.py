# backend/contracts/evidencia.py
import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from .base import (
    ConsultaId,
    Contrato,
    Hash256,
)

Unidad = Literal["COP", "%", "pp", "dias", "unidades", "veces", "lineas"]


class ConsultaRegistrada(Contrato):
    """Una consulta ejecutada contra la capa semántica. Se guarda en `trazas` y se muestra en 'Cómo llegué aquí'.

    El identificador es determinista (hash del SQL renderizado y del corte): la misma consulta al mismo
    corte produce el mismo `consulta_id` y el mismo `resultado_hash`, por lo que es reproducible.
    """
    consulta_id: ConsultaId
    vista: str                                    # vista v_* o tabla base consultada
    descripcion: str = Field(default="", max_length=200)
    sql_renderizado: str
    corte: date
    filas: int = Field(ge=0)
    columnas: list[str] = Field(default_factory=list)
    filas_muestra: list[list[str | int | float | None]] = Field(default_factory=list, max_length=300)
    resultado_hash: Hash256
    ejecutada_en: datetime


class CifraTrazable(Contrato):
    etiqueta: str = Field(max_length=80)
    valor: float
    unidad: Unidad
    consulta_id: ConsultaId


class CitaPolitica(Contrato):
    documento: Literal["FIN-POL-004", "COM-POL-002", "OPE-POL-007"]
    seccion: str = Field(max_length=60)                  # p. ej. "4. Seguimiento y escalamiento"
    fragmento_hash: Hash256                              # hash del texto recuperado de la KB


_ID_O_FECHA = re.compile(
    r"\b(?:P\d{4}|C\d{4}|V\d{2}|PR\d{2}|OC-\d{6}|BOD-[A-Z]{3}|ALR-[\w-]+|FIN-POL-\d+|COM-POL-\d+|OPE-POL-\d+)\b|\d{4}-\d{2}-\d{2}"
)


def numeros_sueltos(texto: str) -> list[str]:
    """Números en texto libre (fuera de IDs y fechas). El pipeline reintenta una vez si hay alguno."""
    return re.findall(r"\d[\d.,]*", _ID_O_FECHA.sub(" ", texto))
