# backend/agents/evidencia.py
"""Ficha de evidencia de una alerta: las cifras que sustentan el diagnóstico, calculadas con SQL registrado.

El Analista no inventa ni calcula números: recibe la ficha (cifras con su `consulta_id`) y las cita con marcadores
`{c1}`, `{c2}`... en su texto. Cada familia de causa (costo, cartera, cobertura, descuentos, inactividad, venta bajo
costo, margen) tiene su propio constructor, que ejecuta consultas registradas sobre la capa semántica.

El `contexto` de la ficha lleva datos estructurados (SKU, OC, niveles de escalamiento...) que usa el playbook del
Estratega para armar las acciones candidatas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from contracts.alertas import Alerta
from contracts.base import TipoEntidad
from contracts.evidencia import CifraTrazable, Unidad
from semantic.db import get_duckdb_connection
from services.registro_consultas import ResultadoConsulta, ejecutar_registrada


@dataclass
class Ficha:
    familia: str
    cifras: list[CifraTrazable] = field(default_factory=list)
    contexto: dict[str, Any] = field(default_factory=dict)
    consulta_politica: str = ""        # texto para buscar el fragmento de política aplicable (vacío = sin política)

    def añadir(self, etiqueta: str, valor: float, unidad: Unidad, res: ResultadoConsulta) -> None:
        self.cifras.append(
            CifraTrazable(etiqueta=etiqueta[:80], valor=float(valor), unidad=unidad, consulta_id=res.consulta.consulta_id)
        )


def _filas(res: ResultadoConsulta) -> list[dict[str, Any]]:
    return [dict(zip(res.columnas, f)) for f in res.filas]


def _entidades(alerta: Alerta, tipo: TipoEntidad) -> list[str]:
    vistos: list[str] = []
    for h in alerta.hallazgos:
        for e in h.entidades:
            if e.tipo == tipo and e.id not in vistos:
                vistos.append(e.id)
    return vistos


def _sql_lista(ids: list[str]) -> str:
    return ", ".join("'" + i.replace("'", "''") + "'" for i in ids)


# -----------------------------------------------------------------------------
# Constructores por familia de causa
# -----------------------------------------------------------------------------
def _ficha_costo(alerta: Alerta, corte: date, con: Any) -> Ficha:
    proveedor = alerta.huella_causa.split("|", 1)[1]
    ficha = Ficha(familia="costo", consulta_politica="costo de un producto sube más de 5%, revisar el precio de venta y margen mínimo por línea")
    res = ejecutar_registrada(
        con,
        """
        WITH costos AS (
            SELECT sku, costo_unitario, fecha_vigencia,
                   lag(costo_unitario) OVER (PARTITION BY sku ORDER BY fecha_vigencia) AS costo_anterior
            FROM costos_proveedor WHERE fecha_vigencia <= fecha_corte()
        ),
        saltos AS (
            SELECT sku, costo_unitario, costo_anterior, fecha_vigencia FROM costos
            WHERE costo_anterior IS NOT NULL AND costo_unitario > costo_anterior * 1.05
              AND fecha_vigencia >= fecha_corte() - INTERVAL 60 DAY
            QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
        ),
        lp AS (
            SELECT sku, precio_lista FROM lista_precios WHERE fecha_vigencia <= fecha_corte()
            QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
        ),
        dem AS (
            SELECT sku, sum(salidas) AS unidades_30d FROM inventario_diario
            WHERE fecha >= fecha_corte() - INTERVAL 30 DAY AND fecha < fecha_corte() GROUP BY sku
        )
        SELECT s.sku, p.linea, s.fecha_vigencia, s.costo_anterior, s.costo_unitario,
               round(100 * (s.costo_unitario / s.costo_anterior - 1), 1) AS pct_alza,
               coalesce(d.unidades_30d, 0) AS unidades_30d, lp.precio_lista,
               round(100 * (1 - s.costo_unitario / lp.precio_lista), 1) AS margen_lista_pct, r.margen_minimo_pct
        FROM saltos s
        JOIN productos p USING (sku)
        JOIN lp USING (sku)
        LEFT JOIN dem d USING (sku)
        JOIN ref_margen_minimo_linea r ON r.linea = p.linea
        WHERE p.proveedor_id = ?
        ORDER BY s.sku
        """,
        [proveedor],
        vista="costos_proveedor",
        corte=corte,
        descripcion="Alza de costo por SKU del proveedor, con unidades de 30 días, precio de lista y margen mínimo de la línea",
    )
    filas = _filas(res)
    if not filas:
        return ficha
    sobrecosto = sum((f["costo_unitario"] - f["costo_anterior"]) * f["unidades_30d"] for f in filas)
    bajo_minimo = [f for f in filas if f["margen_lista_pct"] < f["margen_minimo_pct"]]
    ficha.añadir("Alza de costo del proveedor (máxima entre los SKU)", max(f["pct_alza"] for f in filas), "%", res)
    ficha.añadir("SKU del proveedor con alza de costo", len(filas), "skus", res)
    ficha.añadir("Sobrecosto mensual (unidades de 30 días × alza)", round(sobrecosto), "COP", res)
    ficha.añadir("Margen mínimo de la línea (política)", filas[0]["margen_minimo_pct"], "%", res)
    ficha.añadir("Margen más bajo entre los SKU al precio de lista", min(f["margen_lista_pct"] for f in filas), "%", res)
    ficha.añadir("SKU bajo el margen mínimo con el costo nuevo", len(bajo_minimo), "skus", res)

    linea = filas[0]["linea"]
    res_m = ejecutar_registrada(
        con,
        """
        WITH s AS (
            SELECT semana, margen_pct, row_number() OVER (ORDER BY semana DESC) AS rn
            FROM v_margen_semanal_linea WHERE linea = ? AND semana < date_trunc('week', fecha_corte())
        )
        SELECT round(avg(margen_pct) FILTER (WHERE rn <= 3), 1) AS margen_reciente,
               round(avg(margen_pct) FILTER (WHERE rn BETWEEN 4 AND 11), 1) AS margen_previo
        FROM s
        """,
        [linea],
        vista="v_margen_semanal_linea",
        corte=corte,
        descripcion="Margen de la línea en las últimas 3 semanas completas frente al promedio de las 8 previas",
    )
    m = _filas(res_m)[0] if res_m.filas else {}
    if m.get("margen_reciente") is not None and m.get("margen_previo") is not None:
        ficha.añadir("Margen de la línea, últimas tres semanas", m["margen_reciente"], "%", res_m)
        ficha.añadir("Margen de la línea, ocho semanas previas", m["margen_previo"], "%", res_m)
    ficha.contexto = {"proveedor_id": proveedor, "linea": linea, "skus": filas, "sobrecosto_mensual": round(sobrecosto)}
    return ficha


def _ficha_margen(alerta: Alerta, corte: date, con: Any) -> Ficha:
    linea = alerta.huella_causa.split("|", 1)[1]
    ficha = Ficha(familia="margen", consulta_politica="ninguna línea debe operar por debajo de su margen mínimo")
    res = ejecutar_registrada(
        con,
        """
        WITH s AS (
            SELECT semana, margen_pct, row_number() OVER (ORDER BY semana DESC) AS rn
            FROM v_margen_semanal_linea WHERE linea = ? AND semana < date_trunc('week', fecha_corte())
        )
        SELECT round(avg(margen_pct) FILTER (WHERE rn <= 3), 1) AS margen_reciente,
               round(avg(margen_pct) FILTER (WHERE rn BETWEEN 4 AND 11), 1) AS margen_previo,
               (SELECT margen_minimo_pct FROM ref_margen_minimo_linea WHERE linea = ?) AS margen_minimo
        FROM s
        """,
        [linea, linea],
        vista="v_margen_semanal_linea",
        corte=corte,
        descripcion="Margen de la línea frente a su promedio previo y al margen mínimo",
    )
    f = _filas(res)[0]
    ficha.añadir("Margen de la línea, últimas tres semanas", f["margen_reciente"], "%", res)
    ficha.añadir("Margen de la línea, ocho semanas previas", f["margen_previo"], "%", res)
    ficha.añadir("Margen mínimo de la línea (política)", f["margen_minimo"], "%", res)
    # SKU de la línea con menor margen al precio de lista, ponderados por sus ventas (candidatos a ajuste de precio)
    res_s = ejecutar_registrada(
        con,
        """
        WITH lp AS (
            SELECT sku, precio_lista FROM lista_precios WHERE fecha_vigencia <= fecha_corte()
            QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
        ),
        cs AS (
            SELECT sku, costo_unitario FROM costos_proveedor WHERE fecha_vigencia <= fecha_corte()
            QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
        ),
        dem AS (
            SELECT sku, sum(salidas) AS unidades_30d FROM inventario_diario
            WHERE fecha >= fecha_corte() - INTERVAL 30 DAY AND fecha < fecha_corte() GROUP BY sku
        )
        SELECT p.sku, p.linea, cs.costo_unitario, lp.precio_lista, coalesce(d.unidades_30d, 0) AS unidades_30d,
               round(100 * (1 - cs.costo_unitario / lp.precio_lista), 1) AS margen_lista_pct, r.margen_minimo_pct
        FROM productos p JOIN lp USING (sku) JOIN cs USING (sku) LEFT JOIN dem d USING (sku)
        JOIN ref_margen_minimo_linea r ON r.linea = p.linea
        WHERE p.linea = ? AND 100 * (1 - cs.costo_unitario / lp.precio_lista) < r.margen_minimo_pct
        ORDER BY coalesce(d.unidades_30d, 0) * lp.precio_lista DESC LIMIT 5
        """,
        [linea], vista="productos", corte=corte,
        descripcion="SKU de la línea con margen al precio de lista bajo el mínimo, ordenados por ventas de 30 días",
    )
    filas = _filas(res_s)
    if filas:
        ficha.añadir("SKU de la línea bajo el margen mínimo al precio de lista", len(filas), "skus", res_s)
    ficha.contexto = {"linea": linea, "skus": filas}
    return ficha


def _ficha_cartera(alerta: Alerta, corte: date, con: Any) -> Ficha:
    cliente = alerta.huella_causa.split("|", 1)[1]
    ficha = Ficha(familia="saldo_vencido", consulta_politica="seguimiento y escalamiento de cartera vencida por días de mora, cupo de crédito y plazo de pago")
    res = ejecutar_registrada(
        con,
        "SELECT cliente_id, segmento, plazo_dias, cupo_credito, saldo_abierto, saldo_vencido, max_dias_vencido, dias_pago_prom_120d FROM v_cartera_cliente WHERE cliente_id = ?",
        [cliente], vista="v_cartera_cliente", corte=corte,
        descripcion="Cartera del cliente: saldo abierto y vencido, días de mora, cupo y plazo",
    )
    fila = _filas(res)[0] if res.filas else {}
    dias = int(fila.get("max_dias_vencido") or 0)
    ficha.añadir("Saldo vencido", round(fila.get("saldo_vencido") or 0), "COP", res)
    ficha.añadir("Días del saldo más antiguo vencido", dias, "dias", res)
    ficha.añadir("Saldo abierto total", round(fila.get("saldo_abierto") or 0), "COP", res)
    ficha.añadir("Cupo de crédito", round(fila.get("cupo_credito") or 0), "COP", res)
    ficha.añadir("Plazo de pago pactado", fila.get("plazo_dias") or 0, "dias", res)

    res_p = ejecutar_registrada(
        con,
        "SELECT mes_factura, dias_pago_prom, facturas_pagadas FROM v_dias_pago_mensual WHERE cliente_id = ? ORDER BY mes_factura",
        [cliente], vista="v_dias_pago_mensual", corte=corte,
        descripcion="Días promedio de pago del cliente por mes de factura",
    )
    meses = _filas(res_p)
    if len(meses) >= 2:
        ficha.añadir("Días de pago en su primer mes de historia", meses[0]["dias_pago_prom"], "dias", res_p)
        ficha.añadir("Días de pago en el último mes", meses[-1]["dias_pago_prom"], "dias", res_p)
    ficha.contexto = {
        "cliente_id": cliente,
        "dias_vencido": dias,
        "saldo_vencido": round(fila.get("saldo_vencido") or 0),
        "exceso_cupo": max(round((fila.get("saldo_abierto") or 0) - (fila.get("cupo_credito") or 0)), 0),
        "segmento": fila.get("segmento"),
    }
    return ficha


def _ficha_cobertura(alerta: Alerta, corte: date, con: Any) -> Ficha:
    sku = alerta.huella_causa.split("|", 1)[1]
    bodegas = _entidades(alerta, TipoEntidad.BODEGA)
    ficha = Ficha(familia="cobertura_dias", consulta_politica="cobertura mínima por clase, orden de compra retrasada, contactar proveedor, entrega parcial")
    res = ejecutar_registrada(
        con,
        "SELECT sku, bodega_id, clase_abc, proveedor_id, existencia, demanda_prom_30d, cobertura_dias, unidades_pendientes FROM v_cobertura_inventario WHERE sku = ? ORDER BY cobertura_dias",
        [sku], vista="v_cobertura_inventario", corte=corte,
        descripcion="Existencia, demanda, cobertura y pedidos pendientes del SKU por bodega",
    )
    filas = _filas(res)
    fila = next((f for f in filas if f["bodega_id"] in bodegas), filas[0] if filas else {})
    if not fila:
        return ficha
    ficha.añadir("Cobertura de inventario", fila["cobertura_dias"] or 0, "dias", res)
    ficha.añadir("Demanda diaria promedio (30 días)", fila["demanda_prom_30d"] or 0, "unidades", res)
    ficha.añadir("Existencia actual", fila["existencia"] or 0, "unidades", res)
    ficha.añadir("Unidades de pedidos pendientes de despacho", fila["unidades_pendientes"] or 0, "unidades", res)

    res_oc = ejecutar_registrada(
        con,
        """
        SELECT o.oc_id, o.proveedor_id, o.bodega_id, o.fecha_oc, o.fecha_esperada, o.fecha_recibida, o.cantidad,
               greatest(date_diff('day', o.fecha_esperada, fecha_corte()), 0) AS dias_retraso, pr.lead_time_dias
        FROM ordenes_compra o JOIN proveedores pr USING (proveedor_id)
        WHERE o.sku = ? AND o.bodega_id = ? AND o.fecha_oc <= fecha_corte()
          AND (o.fecha_recibida IS NULL OR o.fecha_recibida > fecha_corte())
        ORDER BY o.fecha_esperada
        """,
        [sku, fila["bodega_id"]], vista="ordenes_compra", corte=corte,
        descripcion="Órdenes de compra del SKU en la bodega que aún no se reciben al corte",
    )
    ocs = _filas(res_oc)
    oc = ocs[0] if ocs else None
    if oc:
        ficha.añadir("Unidades de la orden de compra pendiente", oc["cantidad"], "unidades", res_oc)
        ficha.añadir("Días de retraso de la orden de compra", oc["dias_retraso"], "dias", res_oc)
        ficha.añadir("Lead time habitual del proveedor", oc["lead_time_dias"], "dias", res_oc)
    ficha.contexto = {"sku": sku, "bodega_id": fila["bodega_id"], "proveedor_id": fila.get("proveedor_id"), "oc": oc}
    return ficha


def _ficha_descuentos(alerta: Alerta, corte: date, con: Any) -> Ficha:
    vendedor = alerta.huella_causa.split("|", 1)[1]
    ficha = Ficha(familia="descuento_en_exceso", consulta_politica="topes de descuento por segmento, aprobación especial, vendedor con descuentos fuera de política dos semanas")
    res = ejecutar_registrada(
        con,
        """
        SELECT segmento, count(*) AS lineas, round(sum(descuento_en_exceso)) AS exceso, round(avg(descuento_pct), 1) AS dto_promedio,
               max(tope_descuento_pct) AS tope, count(DISTINCT date_trunc('week', fecha)) AS semanas, min(fecha) AS desde, max(fecha) AS hasta
        FROM v_descuentos_fuera_politica WHERE vendedor_id = ? GROUP BY segmento ORDER BY exceso DESC
        """,
        [vendedor], vista="v_descuentos_fuera_politica", corte=corte,
        descripcion="Descuentos sobre el tope sin aprobación del vendedor, por segmento de cliente",
    )
    filas = _filas(res)
    if not filas:
        return ficha
    res_s = ejecutar_registrada(
        con,
        "SELECT count(DISTINCT date_trunc('week', fecha)) AS semanas, count(*) AS lineas, round(sum(descuento_en_exceso)) AS exceso FROM v_descuentos_fuera_politica WHERE vendedor_id = ?",
        [vendedor], vista="v_descuentos_fuera_politica", corte=corte,
        descripcion="Semanas distintas y total de líneas fuera de política del vendedor",
    )
    t = _filas(res_s)[0]
    principal = filas[0]
    ficha.añadir("Líneas con descuento sobre el tope sin aprobación", t["lineas"], "lineas", res_s)
    ficha.añadir("Descuento en exceso acumulado", t["exceso"], "COP", res_s)
    ficha.añadir("Semanas distintas con descuentos fuera de política", t["semanas"], "semanas", res_s)
    ficha.añadir("Descuento promedio en el segmento más afectado", principal["dto_promedio"], "%", res)
    ficha.añadir("Tope sin aprobación de ese segmento (política)", principal["tope"], "%", res)
    ficha.contexto = {"vendedor_id": vendedor, "semanas": int(t["semanas"]), "lineas": int(t["lineas"]), "desde": principal["desde"]}
    return ficha


def _ficha_inactividad(alerta: Alerta, corte: date, con: Any) -> Ficha:
    cliente = alerta.huella_causa.split("|", 1)[1]
    ficha = Ficha(familia="veces_intervalo_habitual")
    res = ejecutar_registrada(
        con,
        """
        SELECT a.cliente_id, a.pedidos, a.ultima_compra, a.intervalo_prom_dias, a.dias_sin_comprar, a.veces_intervalo_habitual,
               c.vendedor_id, c.segmento
        FROM v_actividad_cliente a JOIN clientes c USING (cliente_id) WHERE a.cliente_id = ?
        """,
        [cliente], vista="v_actividad_cliente", corte=corte,
        descripcion="Frecuencia habitual de compra del cliente frente a los días que lleva sin comprar",
    )
    fila = _filas(res)[0] if res.filas else {}
    if not fila:
        return ficha
    ficha.añadir("Veces su intervalo habitual de compra sin comprar", fila["veces_intervalo_habitual"] or 0, "veces", res)
    ficha.añadir("Días sin comprar", fila["dias_sin_comprar"] or 0, "dias", res)
    ficha.añadir("Intervalo habitual entre pedidos", fila["intervalo_prom_dias"] or 0, "dias", res)
    ficha.añadir("Pedidos históricos del cliente", fila["pedidos"] or 0, "pedidos", res)
    riesgo = next((h.dinero_en_riesgo_cop for h in alerta.hallazgos), 0)
    res_v = ejecutar_registrada(
        con,
        "WITH ult AS (SELECT max(fecha) AS m FROM v_ventas WHERE cliente_id = ?) SELECT coalesce(round(sum(v.valor_neto) / 3.0), 0) AS ventas_mensuales FROM v_ventas v, ult WHERE v.cliente_id = ? AND v.fecha >= ult.m - INTERVAL 90 DAY AND v.fecha <= ult.m",
        [cliente, cliente], vista="v_ventas", corte=corte,
        descripcion="Ventas mensuales promedio del cliente en sus últimos 90 días de actividad",
    )
    ficha.añadir("Ventas mensuales del cliente (últimos 90 días de actividad)", _filas(res_v)[0]["ventas_mensuales"] if res_v.filas else riesgo, "COP", res_v)
    ficha.contexto = {"cliente_id": cliente, "vendedor_id": fila["vendedor_id"], "segmento": fila["segmento"]}
    return ficha


def _ficha_bajo_costo(alerta: Alerta, corte: date, con: Any) -> Ficha:
    sku = alerta.huella_causa.split("|", 1)[1]
    ficha = Ficha(familia="venta_bajo_costo", consulta_politica="prohibido vender por debajo del costo sin aprobación de la Gerencia General")
    res = ejecutar_registrada(
        con,
        """
        SELECT sku, count(*) AS lineas, round(sum(costo_total - valor_neto)) AS perdida,
               round(avg(descuento_pct), 1) AS dto_registrado,
               round(avg(100 * (1 - precio_unitario / precio_lista)), 1) AS desvio_precio_lista,
               round(avg(100 * (1 - (costo_total / cantidad) / precio_lista)), 1) AS margen_lista_pct
        FROM v_ventas WHERE sku = ? AND valor_neto < costo_total GROUP BY sku
        """,
        [sku], vista="v_ventas", corte=corte,
        descripcion="Líneas vendidas por debajo del costo del SKU, su pérdida directa y su precio frente a la lista",
    )
    f = _filas(res)[0] if res.filas else {}
    if f:
        ficha.añadir("Líneas vendidas por debajo del costo", f["lineas"], "lineas", res)
        ficha.añadir("Pérdida directa acumulada", f["perdida"], "COP", res)
        ficha.añadir("Precio facturado por debajo del precio de lista (promedio)", f["desvio_precio_lista"], "%", res)
        ficha.añadir("Descuento registrado en esas líneas (promedio)", f["dto_registrado"], "%", res)
        ficha.añadir("Margen del SKU al precio de lista", f["margen_lista_pct"], "%", res)
    ficha.contexto = {"sku": sku}
    return ficha


_CONSTRUCTORES = {
    "costo": _ficha_costo,
    "margen": _ficha_margen,
    "saldo_vencido": _ficha_cartera,
    "cobertura_dias": _ficha_cobertura,
    "descuento_en_exceso": _ficha_descuentos,
    "veces_intervalo_habitual": _ficha_inactividad,
    "venta_bajo_costo": _ficha_bajo_costo,
}


def construir_ficha(alerta: Alerta, corte: date | None = None, con: Any = None) -> Ficha:
    """Ficha de evidencia de la alerta (cifras trazables y contexto para el playbook)."""
    familia = alerta.huella_causa.split("|", 1)[0]
    constructor = _CONSTRUCTORES.get(familia)
    if constructor is None:
        return Ficha(familia=familia)
    fecha = corte or alerta.hallazgos[0].corte
    cerrar = con is None
    if con is None:
        con = get_duckdb_connection(fecha)
    try:
        return constructor(alerta, fecha, con)
    finally:
        if cerrar:
            con.close()
