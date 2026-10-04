# backend/contracts/operacion.py
from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import Field

from .base import AlertaId, ConsultaId, Contrato
from .evidencia import CifraTrazable


class TrazaLLM(Contrato):
    """Una llamada a Bedrock. Alimenta `trazas` (costo por alerta) y las métricas EMF."""
    run_id: str
    alerta_id: AlertaId | None = None
    agente: Literal["analista", "estratega", "chat"]
    modelo: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    tokens_cache_lectura: int = Field(default=0, ge=0)
    latencia_ms: int = Field(ge=0)
    costo_usd: float = Field(ge=0)
    guardrail_intervino: bool = False
    consulta_ids: list[ConsultaId] = Field(default_factory=list)
    reintentos: int = Field(default=0, ge=0)
    error: str | None = None
    ts: datetime


class ChatRequest(Contrato):
    alerta_id: AlertaId | None = None                    # chat anclado o libre
    mensaje: str = Field(min_length=1, max_length=2000)


class ChatToken(Contrato):
    evento: Literal["token"] = "token"
    texto: str


class ChatCifra(Contrato):
    evento: Literal["cifra"] = "cifra"
    cifra: CifraTrazable


class ChatFin(Contrato):
    evento: Literal["fin"] = "fin"
    consulta_ids: list[ConsultaId]
    costo_usd: float


class ChatError(Contrato):
    evento: Literal["error"] = "error"
    codigo: str
    mensaje: str


ChatEvento = Annotated[Union[ChatToken, ChatCifra, ChatFin, ChatError], Field(discriminator="evento")]


class ErrorAPI(Contrato):
    codigo: Literal[
        "validacion",
        "no_autorizado",
        "no_encontrado",
        "transicion_invalida",
        "conflicto_version",
        "sin_evidencia",
        "guardrail_bloqueo",
        "limite_costo",
        "interno",
    ]
    mensaje: str
    request_id: str
    detalle: dict | None = None


class SimulacionResp(Contrato):
    """Respuesta a POST /simulacion/avanzar y POST /simulacion/reiniciar (Handshake H1)."""
    run_id: str
    corte: date
    dias_avanzados: int = Field(ge=0)
    alertas_detectadas: int = Field(default=0, ge=0)   # causas que el Vigía detecta al nuevo corte
    alertas_nuevas: int = Field(default=0, ge=0)       # causas detectadas por primera vez
