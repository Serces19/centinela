# backend/agents/playbook.py
"""Playbook del Estratega: acciones candidatas derivadas de la política y de la ficha de evidencia.

Los parámetros de cada acción (qué SKU, qué nivel de escalamiento, qué porcentaje, qué OC) los decide este módulo con
reglas de política y datos reales: no los inventa el modelo. El modelo solo elige entre las candidatas, ordena y
justifica (ver estratega.py).

Reglas:
- Cartera: nivel de escalamiento por días vencidos (FIN-POL-004 §4): >60 bloqueo, 31-60 solo contado, 16-30 llamada,
  1-15 recordatorio.
- Descuentos: dos semanas fuera de política pierden la facultad de cotizar (COM-POL-002 §5).
- Cobertura: contactar al proveedor el mismo día, evaluar entrega parcial o proveedor alterno (OPE-POL-007 §3).
- Costo: ajuste de precio que repone el margen mínimo de la línea, ponderado por ventas, más renegociación (OPE-POL-007 §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from contracts.agentes import (
    AjustePrecio,
    ContactoCartera,
    CorregirVentaBajoCosto,
    ExpeditarOC,
    ParametrosAccion,
    ReactivarCliente,
    RenegociarProveedor,
    RevisionDescuentos,
)
from contracts.alertas import Alerta
from contracts.evidencia import CifraTrazable
from agents.evidencia import Ficha
from services.umbrales import Umbrales

NIVELES_CARTERA = ["recordatorio", "llamada_acuerdo", "solo_contado", "bloqueo_despachos"]


@dataclass
class Candidata:
    parametros: ParametrosAccion
    titulo: str                                   # título determinista (se usa si el modelo no responde)
    razon: str                                    # razón determinista, sin números
    cifras_extra: list[CifraTrazable] = field(default_factory=list)   # cifras propias de la acción (p. ej. el ajuste)
    rechazada_antes: bool = False


def _nivel_cartera(dias: int, exceso_cupo: int) -> int:
    if dias > 60:
        return 3
    if dias > 30:
        return 2
    if dias > 15:
        return 1
    return 0


def _pct_ajuste(skus: list[dict]) -> tuple[float, list[str]]:
    """Ajuste de precio (%) que repone el margen mínimo de la línea, ponderado por ventas de 30 días."""
    pesos, necesidades, afectados = [], [], []
    for f in skus:
        minimo = float(f["margen_minimo_pct"]) / 100.0
        precio_necesario = float(f["costo_unitario"]) / (1.0 - minimo)
        necesidad = max(precio_necesario / float(f["precio_lista"]) - 1.0, 0.0) * 100.0
        if necesidad > 0:
            afectados.append(str(f["sku"]))
            pesos.append(max(float(f["unidades_30d"]) * float(f["precio_lista"]), 1.0))
            necesidades.append(necesidad)
    if not afectados:
        return 0.0, []
    ponderado = sum(p * n for p, n in zip(pesos, necesidades)) / sum(pesos)
    return min(30.0, max(0.5, math.ceil(ponderado * 2) / 2)), afectados


def generar_candidatas(alerta: Alerta, ficha: Ficha, umbrales: Umbrales) -> list[Candidata]:
    """Acciones candidatas (hasta 3) para la alerta, en orden de preferencia de la política."""
    ctx = ficha.contexto
    familia = ficha.familia
    base = ficha.cifras[0].consulta_id if ficha.cifras else None
    candidatas: list[Candidata] = []

    if familia in ("costo", "margen") and ctx.get("skus"):
        pct, afectados = _pct_ajuste(ctx["skus"])
        if pct > 0 and base:
            candidatas.append(
                Candidata(
                    AjustePrecio(skus=afectados[:20], pct_ajuste=pct),
                    "Ajustar el precio de venta para reponer el margen mínimo",
                    "Reponer el margen mínimo de la línea trasladando el costo nuevo a la lista de precios, como exige la política de revisión de precios.",
                    [CifraTrazable(etiqueta="Ajuste de precio propuesto", valor=pct, unidad="%", consulta_id=base)],
                )
            )
        if familia == "costo":
            candidatas.append(
                Candidata(
                    RenegociarProveedor(proveedor_id=ctx["proveedor_id"], skus=[str(f["sku"]) for f in ctx["skus"]][:20]),
                    "Renegociar el costo con el proveedor",
                    "Pedir al proveedor que revierta o compense el alza de costo antes de trasladarla al precio de venta.",
                )
            )

    elif familia == "saldo_vencido":
        nivel = _nivel_cartera(int(ctx["dias_vencido"]), int(ctx["exceso_cupo"]))
        titulos = {
            0: "Recordar el pago al cliente",
            1: "Llamar al cliente y acordar un pago",
            2: "Pasar al cliente a pedidos solo de contado",
            3: "Bloquear despachos y escalar a la Dirección Financiera",
        }
        razones = {
            0: "El saldo supera el cupo o el plazo: un recordatorio de pago es el primer paso de la política de cartera.",
            1: "La política de cartera exige llamada, acuerdo de pago y aviso al vendedor para este nivel de mora.",
            2: "La política de cartera indica que, con esta mora, los pedidos nuevos deben ser solo de contado.",
            3: "La política de cartera ordena bloquear despachos y escalar a la Dirección Financiera.",
        }
        for n in [nivel, nivel - 1]:
            if n >= 0:
                candidatas.append(
                    Candidata(ContactoCartera(cliente_id=ctx["cliente_id"], nivel=NIVELES_CARTERA[n]), titulos[n], razones[n])
                )

    elif familia == "cobertura_dias" and ctx.get("oc"):
        oc = ctx["oc"]
        base_oc = dict(oc_id=oc["oc_id"], proveedor_id=oc["proveedor_id"], sku=ctx["sku"], bodega_id=ctx["bodega_id"])
        retraso = int(oc.get("dias_retraso") or 0) > int(oc.get("lead_time_dias") or 0)
        vias = [
            ("contactar_proveedor", "Contactar hoy al proveedor para expeditar la orden", "La política exige contactar al proveedor el mismo día cuando una orden se retrasa."),
            ("entrega_parcial", "Pedir una entrega parcial urgente", "Una entrega parcial urgente cubre la demanda mientras llega el resto de la orden."),
        ]
        if retraso:
            vias.append(("proveedor_alterno", "Evaluar un proveedor alterno", "El retraso supera el tiempo de entrega habitual: la política pide evaluar un proveedor alterno."))
        for via, titulo, razon in vias:
            candidatas.append(Candidata(ExpeditarOC(via=via, **base_oc), titulo, razon))

    elif familia == "descuento_en_exceso":
        suspender = int(ctx["semanas"]) >= umbrales.descuento_semanas
        pares = [
            ("suspender_facultad_cotizar", "Quitar al vendedor la facultad de cotizar sin revisión", "La política retira la facultad de cotizar a quien excede el tope en semanas consecutivas."),
            ("revision_previa_cotizacion", "Exigir revisión previa de las cotizaciones del vendedor", "Mientras se revisa el caso, toda cotización con descuento pasa por Control Comercial."),
        ]
        if not suspender:
            pares.reverse()
        for medida, titulo, razon in pares:
            candidatas.append(Candidata(RevisionDescuentos(vendedor_id=ctx["vendedor_id"], medida=medida), titulo, razon))

    elif familia == "veces_intervalo_habitual":
        for canal, titulo, razon in [
            ("visita", "Visitar al cliente para recuperar su pedido habitual", "Una visita del vendedor es la forma más directa de entender por qué dejó de comprar."),
            ("llamada", "Llamar al cliente para retomar sus pedidos", "Una llamada rápida del vendedor puede reactivar al cliente a bajo costo."),
            ("oferta", "Enviar una oferta de reactivación", "Una oferta comercial puede reactivar un cliente que dejó de comprar."),
        ]:
            candidatas.append(Candidata(ReactivarCliente(cliente_id=ctx["cliente_id"], vendedor_id=ctx["vendedor_id"], canal=canal), titulo, razon))

    elif familia == "venta_bajo_costo":
        candidatas.append(
            Candidata(
                CorregirVentaBajoCosto(skus=[ctx["sku"]]),
                "Corregir el precio facturado del SKU y bloquear ventas bajo costo",
                "Vender por debajo del costo está prohibido sin aprobación de la Gerencia General: hay que corregir el precio base.",
            )
        )

    return candidatas[:3]
