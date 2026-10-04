# backend/contracts/base.py
import hashlib
import json
import re
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0"


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def _id(pattern: str):
    return Annotated[str, StringConstraints(pattern=pattern)]


ClienteId = _id(r"^C\d{4}$")
SkuId = _id(r"^P\d{4}$")
VendedorId = _id(r"^V\d{2}$")
ProveedorId = _id(r"^PR\d{2}$")
BodegaId = _id(r"^BOD-[A-Z]{3}$")
OcId = _id(r"^OC-\d{6}$")
AlertaId = _id(r"^ALR-\d{8}-[0-9a-f]{6}$")   # ALR-<corte yyyymmdd>-<6 hex>
ConsultaId = _id(r"^Q-[0-9a-f]{12}$")
AccionId = _id(r"^ACC-[0-9a-f]{8}$")
Hash256 = _id(r"^[0-9a-f]{64}$")
Pesos = int                                    # COP enteros
Confianza = Annotated[float, Field(ge=0.0, le=1.0)]
CERO_HASH = "0" * 64


class Kpi(StrEnum):
    MARGEN = "margen_pct"
    SALDO_VENCIDO = "saldo_vencido"
    DIAS_PAGO = "dias_pago_prom"
    COBERTURA = "cobertura_dias"
    DESCUENTO_EXCESO = "descuento_en_exceso"
    INTERVALO_COMPRA = "veces_intervalo_habitual"
    VENTA_BAJO_COSTO = "venta_bajo_costo"        # regla extra (COM-POL-002 §4)


class Vista(StrEnum):
    VENTAS = "v_ventas"
    MARGEN_SEMANAL = "v_margen_semanal_linea"
    CARTERA = "v_cartera_cliente"
    DIAS_PAGO = "v_dias_pago_mensual"
    COBERTURA = "v_cobertura_inventario"
    DESCUENTOS = "v_descuentos_fuera_politica"
    ACTIVIDAD = "v_actividad_cliente"


class Severidad(StrEnum):
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class EstadoAlerta(StrEnum):
    NUEVA = "nueva"
    EN_ANALISIS = "en_analisis"
    PROPUESTA = "propuesta"
    SIN_EVIDENCIA = "sin_evidencia"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    EJECUTADA = "ejecutada"
    FALLIDA = "fallida"


TRANSICIONES: dict[EstadoAlerta, set[EstadoAlerta]] = {
    EstadoAlerta.NUEVA: {EstadoAlerta.EN_ANALISIS, EstadoAlerta.FALLIDA},
    EstadoAlerta.EN_ANALISIS: {EstadoAlerta.PROPUESTA, EstadoAlerta.SIN_EVIDENCIA, EstadoAlerta.FALLIDA},
    EstadoAlerta.PROPUESTA: {EstadoAlerta.APROBADA, EstadoAlerta.RECHAZADA},
    EstadoAlerta.APROBADA: {EstadoAlerta.EJECUTADA, EstadoAlerta.FALLIDA},
    EstadoAlerta.SIN_EVIDENCIA: set(),
    EstadoAlerta.RECHAZADA: {EstadoAlerta.NUEVA},     # reabrir para volver a proponer con lo aprendido
    EstadoAlerta.EJECUTADA: set(),
    EstadoAlerta.FALLIDA: {EstadoAlerta.NUEVA},     # reintento manual
}


class TipoEntidad(StrEnum):
    CLIENTE = "cliente"
    VENDEDOR = "vendedor"
    PROVEEDOR = "proveedor"
    SKU = "sku"
    BODEGA = "bodega"
    LINEA = "linea"
    SEGMENTO = "segmento"


_PATRON_ENTIDAD = {
    TipoEntidad.CLIENTE: r"^C\d{4}$",
    TipoEntidad.VENDEDOR: r"^V\d{2}$",
    TipoEntidad.PROVEEDOR: r"^PR\d{2}$",
    TipoEntidad.SKU: r"^P\d{4}$",
    TipoEntidad.BODEGA: r"^BOD-[A-Z]{3}$",
}


class EntidadRef(Contrato):
    """Referencia por ID. Nunca lleva nombre de persona."""
    tipo: TipoEntidad
    id: str

    @model_validator(mode="after")
    def _formato(self):
        patron = _PATRON_ENTIDAD.get(self.tipo)
        if patron and not re.match(patron, self.id):
            raise ValueError(f"id '{self.id}' no corresponde a tipo {self.tipo}")
        return self


def transicion_valida(origen: EstadoAlerta, destino: EstadoAlerta) -> bool:
    return destino in TRANSICIONES[origen]
