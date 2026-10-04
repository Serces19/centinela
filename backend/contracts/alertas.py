# backend/contracts/alertas.py
from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from .base import (
    AlertaId,
    ConsultaId,
    Contrato,
    EntidadRef,
    EstadoAlerta,
    Kpi,
    Pesos,
    SCHEMA_VERSION,
    Severidad,
    transicion_valida,
)


class Hallazgo(Contrato):
    """Salida determinista del Vigía (sin LLM)."""
    hallazgo_id: str = Field(pattern=r"^H-[0-9a-f]{8}$")
    kpi: Kpi
    regla: str                                  # p. ej. "OPE-POL-007/costo+5%"
    severidad: Severidad
    entidades: list[EntidadRef] = Field(min_length=1)
    valor_observado: float
    umbral: float
    corte: date
    dinero_en_riesgo_cop: Pesos = Field(ge=0)
    consulta_ids: list[ConsultaId] = Field(min_length=1)
    huella_causa: str                           # clave de dedup: kpi + entidad raíz (p. ej. "costo|PR08")


class Alerta(Contrato):
    schema_version: str = SCHEMA_VERSION
    alerta_id: AlertaId
    estado: EstadoAlerta
    huella_causa: str
    hallazgos: list[Hallazgo] = Field(min_length=1)
    severidad: Severidad
    dinero_en_riesgo_cop: Pesos = Field(ge=0)
    corte_creacion: date
    creada_en: datetime
    version: int = Field(ge=1)                  # bloqueo optimista en DynamoDB
    paso_actual: Literal["ninguno", "analista", "estratega"] = "ninguno"   # agente en curso (se muestra en la UI)

    def avanzar(self, destino: EstadoAlerta) -> "Alerta":
        if not transicion_valida(self.estado, destino):
            raise ValueError(f"transición inválida {self.estado} → {destino}")
        return self.model_copy(update={"estado": destino, "version": self.version + 1})


class AlertaVista(Contrato):
    """Representación enriquecida de Alerta para la UI (nombres resueltos y propuesta opcional)."""
    alerta: Alerta
    nombres_resueltos: dict[str, str] = Field(default_factory=dict)   # { "V03": "Carlos Gómez", ... }
    propuesta: Any | None = None                                     # Propuesta si existe
    consultas: list[Any] = Field(default_factory=list)               # ConsultaRegistrada si se requieren


class ResumenAlertas(Contrato):
    """Resumen de la bandeja al corte actual: dinero en riesgo y las decisiones clave."""
    corte: date
    total_dinero_en_riesgo_cop: Pesos = Field(ge=0)       # solo alertas pendientes, una por causa
    pendientes: int = Field(ge=0)
    resueltas: int = Field(ge=0)
    por_severidad: dict[str, int] = Field(default_factory=dict)
    decisiones_clave: list[AlertaVista] = Field(default_factory=list)
