# backend/contracts/decision.py
from typing import Literal

from pydantic import Field, model_validator

from .agentes import ParametrosAccion
from .base import AccionId, AlertaId, Contrato


class DecisionRequest(Contrato):
    """POST /alertas/{id}/decision. Cabecera obligatoria: Idempotency-Key."""
    decision: Literal["aprobar", "editar", "rechazar"]
    accion_ids: list[AccionId] = Field(default_factory=list)
    ediciones: dict[AccionId, ParametrosAccion] = Field(default_factory=dict)
    motivo: str | None = Field(default=None, max_length=500)
    decidido_por: str = Field(pattern=r"^usuario:[a-z0-9_.-]{2,30}$")

    @model_validator(mode="after")
    def _reglas(self):
        if self.decision == "rechazar" and len((self.motivo or "").strip()) < 10:
            raise ValueError("rechazar exige un motivo de al menos 10 caracteres")
        if self.decision == "editar" and not self.ediciones:
            raise ValueError("editar exige al menos una edición")
        if self.decision in ("aprobar", "editar") and not self.accion_ids:
            raise ValueError("aprobar o editar exige accion_ids")
        return self


class Borrador(Contrato):
    artefacto_id: str = Field(pattern=r"^ART-[0-9a-f]{8}$")
    accion_id: AccionId
    tipo: Literal["correo", "tarea", "orden_compra"]
    destino: str = Field(pattern=r"^sandbox://")        # nunca un destino real
    contenido: str = Field(max_length=4000)
    estado: Literal["borrador"] = "borrador"


class ResultadoEjecucion(Contrato):
    alerta_id: AlertaId
    borradores: list[Borrador]
    ok: bool
    error: str | None = None
