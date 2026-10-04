# backend/services/umbrales.py
"""Umbrales del Vigía y niveles de autonomía: valores de política con posibilidad de ajuste.

Los valores por defecto salen de `metricas.yaml` y de las tres políticas (FIN-POL-004, COM-POL-002, OPE-POL-007).
Los cambios se guardan en `centinela_config` (documento `umbrales`) y los lee el Vigía en cada corte.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from services.persistencia import persistencia_service

CLAVE_UMBRALES = "umbrales"
CLAVE_AUTONOMIA = "autonomia"

NIVELES_AUTONOMIA = ("informa", "propone", "ejecuta")
TIPOS_ACCION = (
    "ajuste_precio",
    "renegociar_proveedor",
    "contacto_cartera",
    "expeditar_oc",
    "revision_descuentos",
    "reactivar_cliente",
    "corregir_venta_bajo_costo",
)


@dataclass(frozen=True)
class Umbrales:
    costo_alza_pct: float = 5.0                 # OPE-POL-007 §4: costo +5 % exige revisar precio
    margen_caida_pp: float = 3.0                # metricas.yaml: caída > 3 pp frente a las 8 semanas previas
    dias_mora: int = 15                         # FIN-POL-004 §4: más de 15 días vencido
    dias_pago_aumento_pct: float = 50.0         # FIN-POL-004 §5: días de pago +50 % vs histórico
    cobertura_dias_clase_a: float = 10.0        # OPE-POL-007 §2: clase A, 10 días
    cobertura_dias_critica: float = 5.0         # OPE-POL-007 §2: crítico < 5 días con pedidos pendientes
    descuento_semanas: int = 2                  # COM-POL-002 §5: dos semanas con descuentos fuera de política
    descuento_lineas_min: int = 10              # volumen que alerta aunque sea en una sola semana
    intervalo_veces: float = 3.0                # metricas.yaml: más de 3 veces el intervalo habitual
    intervalo_pedidos_min: int = 10             # solo clientes con 10 o más pedidos
    venta_bajo_costo_min_cop: int = 500_000     # pérdida directa acumulada por SKU que se reporta


# Metadatos para la pantalla de Configuración: etiqueta, unidad, política de origen y rango válido.
META_UMBRALES: dict[str, dict[str, Any]] = {
    "costo_alza_pct": {"kpi": "margen_pct", "etiqueta": "Alza de costo de proveedor que exige revisar el precio", "unidad": "%", "politica": "OPE-POL-007 §4", "min": 1, "max": 50},
    "margen_caida_pp": {"kpi": "margen_pct", "etiqueta": "Caída de margen semanal frente a las 8 semanas previas", "unidad": "pp", "politica": "metricas.yaml", "min": 0.5, "max": 20},
    "dias_mora": {"kpi": "saldo_vencido", "etiqueta": "Días vencidos que activan alerta de cartera", "unidad": "días", "politica": "FIN-POL-004 §4", "min": 1, "max": 120},
    "dias_pago_aumento_pct": {"kpi": "dias_pago_prom", "etiqueta": "Aumento de días de pago frente al histórico del cliente", "unidad": "%", "politica": "FIN-POL-004 §5", "min": 10, "max": 300},
    "cobertura_dias_clase_a": {"kpi": "cobertura_dias", "etiqueta": "Cobertura mínima de SKU clase A", "unidad": "días", "politica": "OPE-POL-007 §2", "min": 1, "max": 60},
    "cobertura_dias_critica": {"kpi": "cobertura_dias", "etiqueta": "Cobertura crítica con pedidos pendientes", "unidad": "días", "politica": "OPE-POL-007 §2", "min": 1, "max": 30},
    "descuento_semanas": {"kpi": "descuento_en_exceso", "etiqueta": "Semanas con descuentos fuera de política", "unidad": "semanas", "politica": "COM-POL-002 §5", "min": 1, "max": 8},
    "descuento_lineas_min": {"kpi": "descuento_en_exceso", "etiqueta": "Líneas fuera de política que alertan en una sola semana", "unidad": "líneas", "politica": "COM-POL-002 §5", "min": 1, "max": 500},
    "intervalo_veces": {"kpi": "veces_intervalo_habitual", "etiqueta": "Veces el intervalo habitual de compra sin comprar", "unidad": "veces", "politica": "metricas.yaml", "min": 1.5, "max": 20},
    "intervalo_pedidos_min": {"kpi": "veces_intervalo_habitual", "etiqueta": "Pedidos mínimos del cliente para evaluar su intervalo", "unidad": "pedidos", "politica": "metricas.yaml", "min": 3, "max": 100},
    "venta_bajo_costo_min_cop": {"kpi": "venta_bajo_costo", "etiqueta": "Pérdida directa acumulada por SKU que se reporta", "unidad": "COP", "politica": "COM-POL-002 §4", "min": 0, "max": 1_000_000_000},
}


class ConfiguracionInvalida(ValueError):
    pass


def _validar_umbrales(valores: dict[str, Any]) -> dict[str, float | int]:
    """Valida nombres, tipos y rangos. Devuelve solo los campos válidos y numéricos."""
    por_tipo = {f.name: f.type for f in fields(Umbrales)}
    limpio: dict[str, float | int] = {}
    for nombre, valor in valores.items():
        if nombre not in por_tipo:
            raise ConfiguracionInvalida(f"Umbral desconocido: '{nombre}'.")
        try:
            num = float(valor)
        except (TypeError, ValueError):
            raise ConfiguracionInvalida(f"El umbral '{nombre}' debe ser numérico.") from None
        meta = META_UMBRALES[nombre]
        if not (meta["min"] <= num <= meta["max"]):
            raise ConfiguracionInvalida(
                f"El umbral '{nombre}' debe estar entre {meta['min']} y {meta['max']} {meta['unidad']}."
            )
        limpio[nombre] = int(num) if por_tipo[nombre] in ("int", int) else num
    return limpio


def cargar_umbrales() -> Umbrales:
    """Umbrales vigentes: defaults de política más los ajustes guardados."""
    guardado = persistencia_service.obtener_config(CLAVE_UMBRALES) or {}
    try:
        return Umbrales(**_validar_umbrales(guardado))
    except ConfiguracionInvalida:
        return Umbrales()


def guardar_umbrales(cambios: dict[str, Any], actor: str) -> Umbrales:
    """Aplica cambios parciales validados y los guarda."""
    actuales = asdict(cargar_umbrales())
    actuales.update(_validar_umbrales(cambios))
    persistencia_service.guardar_config(CLAVE_UMBRALES, actuales, actor)
    return Umbrales(**actuales)


def cargar_autonomia() -> dict[str, str]:
    """Nivel de autonomía por tipo de acción. En el MVP todo queda en `propone`."""
    guardado = persistencia_service.obtener_config(CLAVE_AUTONOMIA) or {}
    return {t: guardado.get(t, "propone") if guardado.get(t, "propone") in NIVELES_AUTONOMIA else "propone" for t in TIPOS_ACCION}


def guardar_autonomia(cambios: dict[str, str], actor: str) -> dict[str, str]:
    actuales = cargar_autonomia()
    for tipo, nivel in cambios.items():
        if tipo not in TIPOS_ACCION:
            raise ConfiguracionInvalida(f"Tipo de acción desconocido: '{tipo}'.")
        if nivel not in NIVELES_AUTONOMIA:
            raise ConfiguracionInvalida(f"Nivel de autonomía inválido: '{nivel}'.")
        actuales[tipo] = nivel
    persistencia_service.guardar_config(CLAVE_AUTONOMIA, actuales, actor)
    return actuales
