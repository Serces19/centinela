# backend/contracts/evidencia.py
import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from .base import (
    ConsultaId,
    Contrato,
    Hash256,
    Vista,
)

Unidad = Literal["COP", "%", "pp", "dias", "unidades", "veces", "lineas"]


class ConsultaRegistrada(Contrato):
    """Una consulta ejecutada por una herramienta. Se guarda en `trazas` y se muestra en 'Cómo llegué aquí'."""
    consulta_id: ConsultaId
    vista: Vista
    sql_renderizado: str
    corte: date
    filas: int = Field(ge=0)
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
