# backend/contracts/agentes.py
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

from .base import (
    AccionId,
    AlertaId,
    BodegaId,
    ClienteId,
    Confianza,
    ConsultaId,
    Contrato,
    OcId,
    Pesos,
    ProveedorId,
    SCHEMA_VERSION,
    SkuId,
    VendedorId,
)
from .evidencia import CifraTrazable, CitaPolitica, numeros_sueltos


class DiagnosticoLLM(Contrato):
    """Esquema de la herramienta `emitir_diagnostico` (tool use de Haiku 4.5)."""
    resumen: str = Field(max_length=220)                # una frase para la bandeja
    causa_raiz: str = Field(max_length=800)
    cifras: list[CifraTrazable]
    politicas: list[CitaPolitica]
    supuestos: list[str] = Field(default_factory=list, max_length=5)
    evidencia_suficiente: bool
    confianza: Confianza

    @model_validator(mode="after")
    def _coherencia(self):
        if self.evidencia_suficiente and not self.cifras:
            raise ValueError("con evidencia suficiente se requiere al menos una cifra trazable")
        if not self.evidencia_suficiente and self.confianza > 0.4:
            raise ValueError("sin evidencia suficiente la confianza no puede superar 0.4")
        if numeros_sueltos(self.resumen + " " + self.causa_raiz):
            raise ValueError("el texto contiene números fuera de `cifras`")
        return self


# --- Parámetros de acción: unión discriminada por `tipo` (lista cerrada de herramientas del Ejecutor) ---
class AjustePrecio(Contrato):
    tipo: Literal["ajuste_precio"] = "ajuste_precio"
    skus: list[SkuId] = Field(min_length=1, max_length=20)
    pct_ajuste: Annotated[float, Field(gt=0, le=30)]


class ContactoCartera(Contrato):
    tipo: Literal["contacto_cartera"] = "contacto_cartera"
    cliente_id: ClienteId
    nivel: Literal["recordatorio", "llamada_acuerdo", "solo_contado", "bloqueo_despachos"]


class ExpeditarOC(Contrato):
    tipo: Literal["expeditar_oc"] = "expeditar_oc"
    oc_id: OcId
    proveedor_id: ProveedorId
    sku: SkuId
    bodega_id: BodegaId
    via: Literal["contactar_proveedor", "proveedor_alterno", "entrega_parcial"]


class RevisionDescuentos(Contrato):
    tipo: Literal["revision_descuentos"] = "revision_descuentos"
    vendedor_id: VendedorId
    medida: Literal["revision_previa_cotizacion", "suspender_facultad_cotizar"]


class ReactivarCliente(Contrato):
    tipo: Literal["reactivar_cliente"] = "reactivar_cliente"
    cliente_id: ClienteId
    vendedor_id: VendedorId
    canal: Literal["visita", "llamada", "oferta"]


class CorregirVentaBajoCosto(Contrato):
    tipo: Literal["corregir_venta_bajo_costo"] = "corregir_venta_bajo_costo"
    skus: list[SkuId] = Field(min_length=1, max_length=20)


ParametrosAccion = Annotated[
    Union[AjustePrecio, ContactoCartera, ExpeditarOC, RevisionDescuentos, ReactivarCliente, CorregirVentaBajoCosto],
    Field(discriminator="tipo"),
]


class AccionLLM(Contrato):
    titulo: str = Field(max_length=120)
    razon: str = Field(max_length=400)
    parametros: ParametrosAccion
    confianza: Confianza


class PropuestaLLM(Contrato):
    """Esquema de la herramienta `emitir_propuesta`. NO contiene montos."""
    acciones: list[AccionLLM] = Field(min_length=1, max_length=3)


class ImpactoCalculado(Contrato):
    """Lo produce `calcular_impacto` (Python/SQL). El LLM solo lo ve, no lo escribe."""
    valor_cop: Pesos
    horizonte: Literal["mensual", "unico"]
    metodo: str                                  # p. ej. "unidades_30d x delta_costo"
    intervalo_cop: tuple[Pesos, Pesos] | None = None
    consulta_ids: list[ConsultaId] = Field(min_length=1)


class Accion(Contrato):
    accion_id: AccionId
    titulo: str
    razon: str
    parametros: ParametrosAccion
    confianza: Confianza
    impacto: ImpactoCalculado


class Propuesta(Contrato):
    schema_version: str = SCHEMA_VERSION
    alerta_id: AlertaId
    diagnostico: DiagnosticoLLM
    acciones: list[Accion] = Field(min_length=1, max_length=3)
    modelo: str                                  # inference profile usado
    generada_en: datetime
