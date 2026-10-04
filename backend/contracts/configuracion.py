# backend/contracts/configuracion.py
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from .base import Contrato

CORTE_INICIAL_LIMPIO: date = date(2026, 6, 18)
FECHA_CORTE_DEFECTO: date = date(2026, 9, 30)

NivelAutonomia = Literal["informa", "propone", "ejecuta"]


class ConfigUmbral(Contrato):
    """Un umbral del Vigía con su valor vigente, su valor de política y su rango válido."""
    nombre: str
    etiqueta: str
    kpi: str
    unidad: str
    politica: str
    valor: float
    defecto: float
    minimo: float
    maximo: float


class ConfiguracionVigia(Contrato):
    """Respuesta de GET /config: umbrales vigentes y autonomía por tipo de acción."""
    umbrales: list[ConfigUmbral]
    autonomia: dict[str, NivelAutonomia]
    actualizado_en: datetime | None = None
    actualizado_por: str | None = None


class ConfiguracionUpdate(Contrato):
    """Cuerpo de PUT /config: cambios parciales de umbrales y de autonomía."""
    umbrales: dict[str, float] = Field(default_factory=dict)
    autonomia: dict[str, NivelAutonomia] = Field(default_factory=dict)
    actor: str = Field(pattern=r"^usuario:[a-z0-9_.-]{2,30}$")
