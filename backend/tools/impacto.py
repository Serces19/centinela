# backend/tools/impacto.py
"""Impacto económico de una acción propuesta: cálculo determinista sobre la capa semántica.

El modelo nunca escribe montos. Cada fórmula ejecuta una consulta registrada (`ConsultaRegistrada`), de modo que
el valor es reproducible y enlazable desde "Cómo llegué aquí". Si no hay datos, el impacto es 0 y se dice; no se
rellena con el riesgo de la alerta.

Fórmulas:
- ajuste_precio:        Σ unidades de 30 días × precio de lista × ajuste %          (margen mensual que se recupera)
- renegociar_proveedor: Σ unidades de 30 días × alza de costo                       (sobrecosto mensual si se revierte)
- contacto_cartera:     saldo vencido del cliente (o exceso sobre el cupo)           (cartera en riesgo, único)
- expeditar_oc:         máx(demanda diaria × precio × días de déficit, pedidos pendientes × precio)  (ventas en riesgo)
- revision_descuentos:  Σ descuento en exceso del vendedor                           (descuento no autorizado, único)
- reactivar_cliente:    ventas mensuales de sus últimos 90 días activos              (ventas mensuales en riesgo)
- corregir_venta_bajo_costo: Σ (costo − valor neto) de las líneas bajo costo         (pérdida directa, único)
"""

from __future__ import annotations

from datetime import date
from typing import Any

from contracts.agentes import ImpactoCalculado, ParametrosAccion
from contracts.alertas import Alerta
from semantic.db import get_duckdb_connection
from services.registro_consultas import ejecutar_registrada


def _lista_sql(ids: list[str]) -> str:
    """Lista de literales para IN (...). Los ids ya están validados por el contrato (patrón de SKU)."""
    return ", ".join("'" + str(i).replace("'", "''") + "'" for i in ids)


def _impacto(res, valor: int, horizonte: str, metodo: str, descripcion: str, intervalo=None) -> ImpactoCalculado:
    return ImpactoCalculado(
        valor_cop=max(int(valor), 0),
        horizonte=horizonte,  # type: ignore[arg-type]
        metodo=metodo,
        descripcion=descripcion,
        intervalo_cop=intervalo,
        consulta_ids=[res.consulta.consulta_id],
    )


def _unidades_y_precio(con: Any, corte: date, skus: list[str]):
    return ejecutar_registrada(
        con,
        f"""
        WITH dem AS (
            SELECT sku, sum(salidas) AS unidades_30d FROM inventario_diario
            WHERE fecha >= fecha_corte() - INTERVAL 30 DAY AND fecha < fecha_corte() GROUP BY sku
        ),
        lp AS (
            SELECT sku, precio_lista FROM lista_precios WHERE fecha_vigencia <= fecha_corte()
            QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
        )
        SELECT lp.sku, coalesce(dem.unidades_30d, 0) AS unidades_30d, lp.precio_lista
        FROM lp LEFT JOIN dem USING (sku) WHERE lp.sku IN ({_lista_sql(skus)}) ORDER BY lp.sku
        """,
        vista="lista_precios",
        corte=corte,
        descripcion="Unidades vendidas en los últimos 30 días y precio de lista vigente de los SKU de la acción",
    )


def calcular_impacto_economico(
    accion_parametros: ParametrosAccion,
    alerta: Alerta,
    corte: date | None = None,
    con: Any = None,
) -> ImpactoCalculado:
    """Impacto económico de la acción (ver fórmulas en la cabecera del módulo)."""
    fecha = corte or alerta.corte_creacion
    cerrar = con is None
    if con is None:
        con = get_duckdb_connection(fecha)
    try:
        p = accion_parametros
        tipo = p.tipo

        if tipo == "ajuste_precio":
            res = _unidades_y_precio(con, fecha, [str(s) for s in p.skus])
            base = sum(float(u) * float(precio) for _, u, precio in res.filas)
            valor = round(base * p.pct_ajuste / 100.0)
            return _impacto(
                res, valor, "mensual", "unidades_30d_x_precio_lista_x_ajuste",
                "Margen mensual adicional: unidades de los últimos 30 días × precio de lista × porcentaje de ajuste.",
                (round(valor * 0.85), valor),
            )

        if tipo == "renegociar_proveedor":
            res = ejecutar_registrada(
                con,
                f"""
                WITH costos AS (
                    SELECT sku, costo_unitario, fecha_vigencia,
                           lag(costo_unitario) OVER (PARTITION BY sku ORDER BY fecha_vigencia) AS costo_anterior
                    FROM costos_proveedor WHERE fecha_vigencia <= fecha_corte() AND proveedor_id = '{p.proveedor_id}'
                ),
                saltos AS (
                    SELECT sku, costo_unitario - costo_anterior AS delta FROM costos
                    WHERE costo_anterior IS NOT NULL AND costo_unitario > costo_anterior * 1.05
                      AND fecha_vigencia >= fecha_corte() - INTERVAL 60 DAY AND sku IN ({_lista_sql([str(s) for s in p.skus])})
                    QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
                ),
                dem AS (
                    SELECT sku, sum(salidas) AS unidades_30d FROM inventario_diario
                    WHERE fecha >= fecha_corte() - INTERVAL 30 DAY AND fecha < fecha_corte() GROUP BY sku
                )
                SELECT s.sku, s.delta, coalesce(d.unidades_30d, 0) AS unidades_30d, round(s.delta * coalesce(d.unidades_30d, 0)) AS sobrecosto
                FROM saltos s LEFT JOIN dem d USING (sku) ORDER BY s.sku
                """,
                vista="costos_proveedor",
                corte=fecha,
                descripcion="Sobrecosto mensual por el alza de costo del proveedor en los SKU de la acción",
            )
            valor = sum(float(f[3]) for f in res.filas)
            return _impacto(res, round(valor), "mensual", "sobrecosto_mensual_proveedor",
                            "Sobrecosto mensual que se evita si el proveedor revierte el alza de costo.")

        if tipo == "contacto_cartera":
            res = ejecutar_registrada(
                con,
                f"SELECT cliente_id, cupo_credito, saldo_abierto, saldo_vencido, max_dias_vencido FROM v_cartera_cliente WHERE cliente_id = '{p.cliente_id}'",
                vista="v_cartera_cliente", corte=fecha,
                descripcion="Saldo vencido y saldo abierto del cliente frente a su cupo de crédito",
            )
            if not res.filas:
                return _impacto(res, 0, "unico", "cartera_en_riesgo", "El cliente no tiene cartera al corte.")
            _, cupo, abierto, vencido, _dias = res.filas[0]
            vencido_i, abierto_i, cupo_i = int(round(vencido or 0)), int(round(abierto or 0)), int(round(cupo or 0))
            valor = vencido_i if vencido_i > 0 else max(abierto_i - cupo_i, 0)
            return _impacto(res, valor, "unico", "cartera_en_riesgo",
                            "Cartera vencida del cliente (o exceso sobre su cupo) que se busca recuperar.",
                            (vencido_i, abierto_i) if abierto_i > vencido_i else None)

        if tipo == "expeditar_oc":
            res = ejecutar_registrada(
                con,
                f"""
                SELECT c.sku, c.bodega_id, c.demanda_prom_30d, c.cobertura_dias, c.unidades_pendientes, p.precio_lista
                FROM v_cobertura_inventario c
                JOIN (SELECT sku, precio_lista FROM lista_precios WHERE fecha_vigencia <= fecha_corte()
                      QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1) p USING (sku)
                WHERE c.sku = '{p.sku}' AND c.bodega_id = '{p.bodega_id}'
                """,
                vista="v_cobertura_inventario", corte=fecha,
                descripcion="Cobertura, demanda, pedidos pendientes y precio de lista del SKU en la bodega",
            )
            if not res.filas:
                return _impacto(res, 0, "unico", "ventas_en_riesgo_quiebre", "El SKU no tiene inventario registrado en la bodega.")
            _, _, demanda, cobertura, pendientes, precio = res.filas[0]
            dias_deficit = max(1.0, 10.0 - float(cobertura or 0.0))
            por_demanda = round(float(demanda or 0) * float(precio or 0) * dias_deficit)
            por_pendientes = round(float(pendientes or 0) * float(precio or 0))
            return _impacto(res, max(por_demanda, por_pendientes), "unico", "ventas_en_riesgo_quiebre",
                            "Ventas en riesgo por el déficit de cobertura o por los pedidos pendientes sin existencia.",
                            (min(por_demanda, por_pendientes), max(por_demanda, por_pendientes)) if por_demanda != por_pendientes else None)

        if tipo == "revision_descuentos":
            res = ejecutar_registrada(
                con,
                f"SELECT vendedor_id, count(*) AS lineas, round(sum(descuento_en_exceso)) AS exceso FROM v_descuentos_fuera_politica WHERE vendedor_id = '{p.vendedor_id}' GROUP BY vendedor_id",
                vista="v_descuentos_fuera_politica", corte=fecha,
                descripcion="Descuento concedido por encima del tope sin aprobación especial, por vendedor",
            )
            valor = int(res.filas[0][2]) if res.filas else 0
            return _impacto(res, valor, "unico", "exceso_descuento", "Descuento otorgado sobre el tope sin aprobación (margen cedido).")

        if tipo == "reactivar_cliente":
            res = ejecutar_registrada(
                con,
                f"""
                WITH ult AS (SELECT max(fecha) AS max_f FROM v_ventas WHERE cliente_id = '{p.cliente_id}')
                SELECT '{p.cliente_id}' AS cliente_id, coalesce(round(sum(v.valor_neto) / 3.0), 0) AS ventas_mensuales
                FROM v_ventas v, ult WHERE v.cliente_id = '{p.cliente_id}' AND v.fecha >= ult.max_f - INTERVAL 90 DAY AND v.fecha <= ult.max_f
                """,
                vista="v_ventas", corte=fecha,
                descripcion="Ventas mensuales del cliente en sus últimos 90 días de actividad",
            )
            valor = int(res.filas[0][1]) if res.filas else 0
            return _impacto(res, valor, "mensual", "ventas_mensuales_en_riesgo",
                            "Ventas mensuales que se pierden si el cliente no vuelve a comprar.",
                            (round(valor * 0.9), round(valor * 1.1)) if valor else None)

        if tipo == "corregir_venta_bajo_costo":
            res = ejecutar_registrada(
                con,
                f"SELECT sku, count(*) AS lineas, round(sum(costo_total - valor_neto)) AS perdida FROM v_ventas WHERE valor_neto < costo_total AND sku IN ({_lista_sql([str(s) for s in p.skus])}) GROUP BY sku ORDER BY sku",
                vista="v_ventas", corte=fecha,
                descripcion="Pérdida directa de las líneas vendidas por debajo del costo, por SKU",
            )
            valor = sum(float(f[2]) for f in res.filas)
            return _impacto(res, round(valor), "unico", "perdida_directa_bajo_costo", "Pérdida directa acumulada por vender bajo el costo.")

        raise ValueError(f"Tipo de acción sin fórmula de impacto: '{tipo}'")
    finally:
        if cerrar:
            con.close()
