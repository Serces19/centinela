# backend/contracts/herramientas.py
from datetime import date
from typing import Literal

from pydantic import Field

from .agentes import DiagnosticoLLM, Propuesta
from .alertas import Hallazgo
from .base import AccionId, AlertaId, Contrato, Hash256, Vista
from .decision import DecisionRequest, ResultadoEjecucion
from .evidencia import ConsultaRegistrada


class Filtro(Contrato):
    columna: str = Field(pattern=r"^[a-z_]{1,40}$")
    op: Literal["=", "!=", "<", "<=", ">", ">=", "in"]
    valor: str | int | float | list[str | int | float]


class ConsultarVistaIn(Contrato):
    vista: Vista
    columnas: list[str] = Field(min_length=1, max_length=20)
    filtros: list[Filtro] = Field(default_factory=list, max_length=8)
    agrupar_por: list[str] = Field(default_factory=list, max_length=4)
    ordenar_por: str | None = None
    limite: int = Field(default=100, ge=1, le=500)


class ConsultarVistaOut(Contrato):
    consulta: ConsultaRegistrada
    columnas: list[str]
    filas: list[list[str | int | float | None]]
    truncado: bool


class BuscarPoliticaIn(Contrato):
    consulta: str = Field(min_length=3, max_length=300)
    k: int = Field(default=3, ge=1, le=5)


class FragmentoPolitica(Contrato):
    documento: Literal["FIN-POL-004", "COM-POL-002", "OPE-POL-007"]
    seccion: str
    texto: str                                   # se inyecta al LLM dentro de <datos_politica>…</datos_politica>
    score: float = Field(ge=0, le=1)
    fragmento_hash: Hash256


class BuscarPoliticaOut(Contrato):
    fragmentos: list[FragmentoPolitica]
    guardrail_ataque_detectado: bool = False     # resultado de ApplyGuardrail sobre los fragmentos


class CalcularImpactoIn(Contrato):
    metodo: Literal[
        "delta_costo_x_unidades_30d",
        "exceso_descuento",
        "cartera_vencida_en_riesgo",
        "margen_perdido_bajo_costo",
        "ventas_perdidas_cliente_inactivo",
        "ventas_perdidas_quiebre",
    ]
    parametros: dict[str, str | int | float | list[str]]


class CrearBorradorIn(Contrato):
    alerta_id: AlertaId
    accion_id: AccionId                          # el Ejecutor solo acepta acciones en estado `aprobada`


class EstadoGrafo(Contrato):
    run_id: str
    corte: date
    alerta_id: AlertaId | None = None
    hallazgos: list[Hallazgo] = Field(default_factory=list)
    diagnostico: DiagnosticoLLM | None = None
    propuesta: Propuesta | None = None
    decision: DecisionRequest | None = None
    resultado: ResultadoEjecucion | None = None


class InterruptPayload(Contrato):
    alerta_id: AlertaId
    propuesta: Propuesta


class PipelineEvent(Contrato):
    run_id: str
    accion: Literal["vigia", "reanudar"]
    corte: date
    alerta_id: AlertaId | None = None
