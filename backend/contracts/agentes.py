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
from .evidencia import CifraTrazable, CitaPolitica, numeros_sueltos, referencias_cifras


class DiagnosticoLLM(Contrato):
    """Diagnóstico del Analista. El texto cita las cifras con marcadores `{c1}`, `{c2}`... (posición en `cifras`)
    y no puede traer números propios; la interfaz sustituye cada marcador por el valor y enlaza su consulta."""
    resumen: str = Field(max_length=220)                # una frase para la bandeja
    causa_raiz: str = Field(max_length=800)
    cifras: list[CifraTrazable]
    politicas: list[CitaPolitica]
    supuestos: list[str] = Field(default_factory=list, max_length=5)
    numeros_politica: list[str] = Field(default_factory=list, max_length=60)   # números que aparecen en la política citada
    evidencia_suficiente: bool
    confianza: Confianza

    @model_validator(mode="after")
    def _coherencia(self):
        if self.evidencia_suficiente and not self.cifras:
            raise ValueError("con evidencia suficiente se requiere al menos una cifra trazable")
        if not self.evidencia_suficiente and self.confianza > 0.4:
            raise ValueError("sin evidencia suficiente la confianza no puede superar 0.4")
        texto = self.resumen + " " + self.causa_raiz
        if numeros_sueltos(texto, self.numeros_politica):
            raise ValueError("el texto contiene números fuera de `cifras`")
        if any(not 1 <= i <= len(self.cifras) for i in referencias_cifras(texto)):
            raise ValueError("el texto cita una cifra que no existe en `cifras`")
        return self


class CitaElegida(Contrato):
    """Política que el modelo elige citar entre los fragmentos recuperados (el servidor añade el hash)."""
    documento: Literal["FIN-POL-004", "COM-POL-002", "OPE-POL-007"]
    seccion: str = Field(max_length=60)


class DiagnosticoBorrador(Contrato):
    """Esquema de la herramienta `emitir_diagnostico` (Haiku 4.5). Sin cifras ni hashes: el servidor los aporta."""
    resumen: str = Field(max_length=220, description="Una frase para la bandeja. Cita cifras solo con marcadores {c1}, {c2}...")
    causa_raiz: str = Field(max_length=800, description="Causa raíz con evidencia. Cita cifras solo con marcadores {cN}.")
    politicas: list[CitaElegida] = Field(default_factory=list, max_length=4)
    supuestos: list[str] = Field(default_factory=list, max_length=5)
    evidencia_suficiente: bool
    confianza: Confianza


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


class RenegociarProveedor(Contrato):
    tipo: Literal["renegociar_proveedor"] = "renegociar_proveedor"
    proveedor_id: ProveedorId
    skus: list[SkuId] = Field(min_length=1, max_length=20)


class CorregirVentaBajoCosto(Contrato):
    tipo: Literal["corregir_venta_bajo_costo"] = "corregir_venta_bajo_costo"
    skus: list[SkuId] = Field(min_length=1, max_length=20)


ParametrosAccion = Annotated[
    Union[
        AjustePrecio, RenegociarProveedor, ContactoCartera, ExpeditarOC,
        RevisionDescuentos, ReactivarCliente, CorregirVentaBajoCosto,
    ],
    Field(discriminator="tipo"),
]


class SeleccionAccion(Contrato):
    """El modelo elige una acción candidata (por número) y la justifica. No toca los parámetros ni escribe montos."""
    candidato: int = Field(ge=1, description="Número del candidato elegido, tal como aparece en la lista")
    titulo: str = Field(max_length=120, description="Título corto de la acción, sin números salvo marcadores {cN}")
    razon: str = Field(max_length=400, description="Por qué esta acción, sin números salvo marcadores {cN}")
    confianza: Confianza


class SeleccionEstratega(Contrato):
    """Esquema de la herramienta `emitir_propuesta`: entre una y tres acciones elegidas de la lista de candidatas."""
    selecciones: list[SeleccionAccion] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def _sin_numeros(self):
        for sel in self.selecciones:
            sueltos = numeros_sueltos(sel.titulo + " " + sel.razon)
            if sueltos:
                raise ValueError(f"el texto contiene números fuera de las cifras: {sueltos}")
        if len({sel.candidato for sel in self.selecciones}) != len(self.selecciones):
            raise ValueError("no se puede elegir dos veces el mismo candidato")
        return self


class ImpactoCalculado(Contrato):
    """Lo produce `calcular_impacto` (Python/SQL). El LLM solo lo ve, no lo escribe."""
    valor_cop: Pesos
    horizonte: Literal["mensual", "unico"]
    metodo: str                                  # p. ej. "unidades_30d x delta_costo"
    descripcion: str = Field(default="", max_length=300)   # qué representa el monto, en una frase
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
    cifras: list[CifraTrazable] = Field(default_factory=list)            # cifras que citan los textos de las acciones ({cN})
    aprendizaje: list[str] = Field(default_factory=list, max_length=5)   # ajustes hechos por rechazos anteriores
    generada_en: datetime
