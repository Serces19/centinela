# backend/contracts/evidencia.py
import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from .base import (
    ConsultaId,
    Contrato,
    Hash256,
)

Unidad = Literal["COP", "%", "pp", "dias", "unidades", "veces", "lineas", "semanas", "pedidos", "skus"]


class ConsultaRegistrada(Contrato):
    """Una consulta ejecutada contra la capa semántica. Se guarda en `trazas` y se muestra en 'Cómo llegué aquí'.

    El identificador es determinista (hash del SQL renderizado y del corte): la misma consulta al mismo
    corte produce el mismo `consulta_id` y el mismo `resultado_hash`, por lo que es reproducible.
    """
    consulta_id: ConsultaId
    vista: str                                    # vista v_* o tabla base consultada
    descripcion: str = Field(default="", max_length=200)
    sql_renderizado: str
    corte: date
    filas: int = Field(ge=0)
    columnas: list[str] = Field(default_factory=list)
    filas_muestra: list[list[str | int | float | None]] = Field(default_factory=list, max_length=300)
    resultado_hash: Hash256
    ejecutada_en: datetime


class CifraTrazable(Contrato):
    etiqueta: str = Field(max_length=80)
    valor: float
    unidad: Unidad
    consulta_id: ConsultaId


class CitaPolitica(Contrato):
    documento: Literal["FIN-POL-004", "COM-POL-002", "OPE-POL-007"]
    seccion: str = Field(max_length=60)                  # p. ej. "4. Seguimiento y escalamiento"
    fragmento_hash: Hash256                              # hash del texto recuperado de la KB


_ID_O_FECHA = re.compile(
    r"\b(?:P\d{4}|C\d{4}|V\d{2}|PR\d{2}|OC-\d{6}|BOD-[A-Z]{3}|ALR-[\w-]+|FIN-POL-\d+|COM-POL-\d+|OPE-POL-\d+)\b|\d{4}-\d{2}-\d{2}"
)
_PLACEHOLDER = re.compile(r"\{c(\d{1,2})\}")
_PALABRAS_NUMERO = re.compile(
    r"\b(?:dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|veinte|veinti\w+|"
    r"treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|doscientos|trescientos|mil|millon|millones)\b",
    re.IGNORECASE,
)


_UNIDAD_REPETIDA = re.compile(r"\b(SKU|líneas?|días?|semanas?|pedidos?|unidades|veces)(?:\s+\1\b)+", re.IGNORECASE)
_SECCION = re.compile(r"§\s*\d+(?:\s*-\s*§?\s*\d+)?")


def normalizar_numero(token: str) -> str:
    return token.strip().rstrip(".,")


def numeros_en(texto: str) -> list[str]:
    """Números (dígitos) que aparecen en un texto, normalizados. Sirve para extraer los umbrales de una política."""
    return sorted({normalizar_numero(t) for t in re.findall(r"\d[\d.,]*", texto)} - {""})


def numeros_sueltos(texto: str, permitidos: "Iterable[str]" = ()) -> list[str]:
    """Números en texto libre: dígitos o palabras de número, fuera de IDs, fechas, secciones (§4) y marcadores `{cN}`.

    Las cifras se citan con marcadores (`{c1}`) que apuntan a `cifras`; el texto no puede traer números propios.
    Excepción: dígitos que aparecen literalmente en la política citada (`permitidos`), p. ej. el umbral "5" de
    "si el costo sube más de 5 %". Las palabras de número nunca se permiten.
    """
    ok = {normalizar_numero(p) for p in permitidos}
    limpio = _SECCION.sub(" ", _PLACEHOLDER.sub(" ", _ID_O_FECHA.sub(" ", texto)))
    digitos = [t for t in re.findall(r"\d[\d.,]*", limpio) if normalizar_numero(t) not in ok]
    palabras = [m.group(0) for m in _PALABRAS_NUMERO.finditer(limpio)]
    return digitos + palabras


def referencias_cifras(texto: str) -> list[int]:
    """Índices (1-based) de las cifras citadas con marcadores `{cN}`."""
    return [int(m.group(1)) for m in _PLACEHOLDER.finditer(texto)]


def formatear_cifra(c: "CifraTrazable") -> str:
    """Valor de la cifra con su unidad, en formato colombiano (punto de miles, coma decimal)."""
    v = c.valor

    def miles(x: float) -> str:
        return f"{round(x):,}".replace(",", ".")

    def dec(x: float) -> str:
        return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0")

    def num(x: float) -> str:
        return miles(x) if abs(x - round(x)) < 0.05 else dec(x)

    if c.unidad == "COP":
        return f"${miles(v)}"
    if c.unidad == "%":
        return f"{dec(v)} %"
    if c.unidad == "pp":
        return f"{dec(v)} pp"
    if c.unidad == "dias":
        return f"{num(v)} {'día' if round(v) == 1 and v == round(v) else 'días'}"
    if c.unidad == "veces":
        return f"{dec(v)} veces"
    if c.unidad == "lineas":
        return f"{miles(v)} {'línea' if round(v) == 1 else 'líneas'}"
    if c.unidad == "semanas":
        return f"{miles(v)} {'semana' if round(v) == 1 else 'semanas'}"
    if c.unidad == "pedidos":
        return f"{miles(v)} {'pedido' if round(v) == 1 else 'pedidos'}"
    if c.unidad == "skus":
        return f"{miles(v)} SKU"
    return f"{num(v)} unidades"


def renderizar_texto(texto: str, cifras: "list[CifraTrazable]") -> str:
    """Sustituye cada `{cN}` por el valor formateado de la cifra N (1-based)."""

    def _sub(m: "re.Match[str]") -> str:
        i = int(m.group(1))
        return formatear_cifra(cifras[i - 1]) if 1 <= i <= len(cifras) else m.group(0)

    return _UNIDAD_REPETIDA.sub(r"\1", _PLACEHOLDER.sub(_sub, texto)).replace("% %", "%")
