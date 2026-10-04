# backend/contracts/operacion.py
from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import ConfigDict, Field

from .base import AlertaId, ConsultaId, Contrato
from .evidencia import CifraTrazable, Unidad


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


class CostoAgente(Contrato):
    agente: str
    llamadas: int = Field(ge=0)
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    costo_usd: float = Field(ge=0)


class ResumenCostos(Contrato):
    """Costo real de inferencia (tokens que reporta Bedrock) acumulado desde el último reinicio de la demo."""
    total_usd: float = Field(ge=0)
    llamadas: int = Field(ge=0)
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    por_agente: list[CostoAgente]
    alertas_analizadas: int = Field(ge=0)
    usd_por_alerta: float | None = None          # promedio por alerta con análisis y propuesta (analista + estratega)
    usd_por_pregunta_chat: float | None = None


class ChatRequest(Contrato):
    alerta_id: AlertaId | None = None                    # chat anclado o libre
    mensaje: str = Field(min_length=1, max_length=2000)


class ChatToken(Contrato):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)   # conserva los espacios entre trozos

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


class ChatPaso(Contrato):
    """Paso en curso mientras Centinela consulta los datos (se muestra en la interfaz)."""
    evento: Literal["paso"] = "paso"
    texto: str


class PuntoGrafico(Contrato):
    etiqueta: str = Field(max_length=60)
    valor: float


class ChatGrafico(Contrato):
    """Serie para pintar un gráfico. Los puntos salen de una consulta registrada, no del modelo."""
    evento: Literal["grafico"] = "grafico"
    titulo: str = Field(max_length=100)
    tipo: Literal["barras", "linea"]
    unidad: Unidad
    consulta_id: ConsultaId
    puntos: list[PuntoGrafico] = Field(min_length=1, max_length=20)


ChatEvento = Annotated[
    Union[ChatPaso, ChatToken, ChatCifra, ChatGrafico, ChatFin, ChatError], Field(discriminator="evento")
]


class RefCifra(Contrato):
    """Cifra que el modelo cita de un resultado de consulta: el servidor lee el valor, el modelo no lo escribe."""
    etiqueta: str = Field(max_length=80)
    unidad: Unidad
    consulta_id: ConsultaId
    columna: str = Field(max_length=60)
    fila: int = Field(ge=0, description="Posición de la fila en el resultado (0 = primera)")


class RefGrafico(Contrato):
    titulo: str = Field(max_length=100)
    tipo: Literal["barras", "linea"]
    unidad: Unidad
    consulta_id: ConsultaId
    columna_etiqueta: str = Field(max_length=60)
    columna_valor: str = Field(max_length=60)


class RespuestaChat(Contrato):
    """Esquema de la herramienta `responder` del chat. El texto cita cifras con marcadores {c1}, {c2}..."""
    texto: str = Field(max_length=1500)
    cifras: list[RefCifra] = Field(default_factory=list, max_length=8)
    grafico: RefGrafico | None = None
    sin_evidencia: bool = False


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
