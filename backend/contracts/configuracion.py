from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from .base import Contrato, Kpi, SCHEMA_VERSION

CORTE_INICIAL_LIMPIO: date = date(2026, 6, 18)
FECHA_CORTE_DEFECTO: date = date(2026, 9, 30)


class ConfigKpi(Contrato):
    """Configuración de monitoreo por KPI (umbral, responsable y nivel de autonomía)."""
    kpi: Kpi
    nombre: str = Field(min_length=3, max_length=100)
    umbral_defecto: float
    umbral_actual: float
    responsable_email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    autonomia: Literal["informa", "propone", "ejecuta"] = "propone"
    activo: bool = True


class CentinelaConfig(Contrato):
    """Registro de la tabla `centinela_config` en DynamoDB."""
    schema_version: str = SCHEMA_VERSION
    clave: str = Field(min_length=1, max_length=100)   # PK en centinela_config
    valor: dict[str, Any]
    actualizado_en: datetime
    actualizado_por: str = Field(pattern=r"^(sistema|usuario:[a-z0-9_.-]{2,30})$")
