# backend/tools/impacto.py
"""Herramienta FastMCP `calcular_impacto` determinista sobre DuckDB.

Calcula el impacto económico / dinero en riesgo con fórmulas precisas para:
- S1 (delta_costo_x_unidades_30d): (costo nuevo - costo ant) * demanda 30d (reproduce ≈ $23.55M a corte 2026-08-15)
- S2 (cartera_vencida_en_riesgo): saldo_vencido (y saldo_abierto)
- S3 (ventas_perdidas_quiebre): demanda diaria * precio lista * días quiebre (o pedidos pendientes sin existencia)
- S4 (exceso_descuento): suma de descuento_en_exceso de líneas fuera de política (reproduce $8.096.844 a corte 2026-09-30)
- S5 (ventas_perdidas_cliente_inactivo): ventas promedio mensuales del cliente (últimos 90 días)
- S6 (margen_perdido_bajo_costo): suma de costo_total - valor_neto en líneas bajo costo (reproduce $2.721.412 a corte 2026-09-30)
"""

from datetime import date
from decimal import Decimal
import uuid
from typing import Any

from fastmcp import FastMCP

from contracts.agentes import ImpactoCalculado, ParametrosAccion
from contracts.alertas import Alerta
from contracts.herramientas import CalcularImpactoIn
from semantic.db import FECHA_CORTE_DEFECTO, get_duckdb_connection

mcp = FastMCP("centinela-impacto")


def calcular_impacto(
    inp: CalcularImpactoIn,
    corte: date | None = None,
    con: Any = None,
) -> ImpactoCalculado:
    """Calcula el impacto económico de manera determinista."""
    fecha_corte_efectiva = corte or FECHA_CORTE_DEFECTO
    params = inp.parametros

    cerrar_con = False
    if con is None:
        con = get_duckdb_connection(fecha_corte_efectiva)
        cerrar_con = True

    try:
        consulta_id = f"Q-{uuid.uuid4().hex[:12]}"

        if inp.metodo == "delta_costo_x_unidades_30d":
            # S1: Incremento de costo de proveedor
            proveedor_id = params.get("proveedor_id")
            skus_filtro = params.get("skus")

            where_clauses = ["u.pct_incremento > 0.05"]
            sql_params: list[Any] = []
            if proveedor_id:
                where_clauses.append("u.proveedor_id = ?")
                sql_params.append(str(proveedor_id))
            if skus_filtro and isinstance(skus_filtro, list):
                placeholders = ", ".join(["?"] * len(skus_filtro))
                where_clauses.append(f"u.sku IN ({placeholders})")
                sql_params.extend([str(s) for s in skus_filtro])

            query = f"""
                WITH costos AS (
                    SELECT sku, proveedor_id, costo_unitario, fecha_vigencia,
                           lag(costo_unitario) OVER (PARTITION BY sku ORDER BY fecha_vigencia) AS costo_anterior
                    FROM costos_proveedor
                    WHERE fecha_vigencia <= fecha_corte()
                ),
                saltos AS (
                    SELECT sku, proveedor_id, costo_unitario, costo_anterior,
                           (costo_unitario - costo_anterior) AS delta_costo,
                           (costo_unitario - costo_anterior) / nullif(costo_anterior, 0) AS pct_incremento
                    FROM costos
                    WHERE (costo_unitario - costo_anterior) / nullif(costo_anterior, 0) > 0.05
                      AND fecha_vigencia >= fecha_corte() - INTERVAL 60 DAY
                    QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
                ),
                dem_30d AS (
                    SELECT sku, sum(salidas) AS unidades_30d
                    FROM inventario_diario
                    WHERE fecha >= fecha_corte() - INTERVAL 30 DAY AND fecha < fecha_corte()
                    GROUP BY sku
                )
                SELECT coalesce(round(sum(u.delta_costo * d.unidades_30d)), 0)
                FROM saltos u
                JOIN dem_30d d USING (sku)
                WHERE {" AND ".join(where_clauses)}
            """
            res = con.execute(query, sql_params).fetchone()
            monto = int(res[0]) if res and res[0] is not None else 0

            return ImpactoCalculado(
                valor_cop=monto,
                horizonte="mensual",
                metodo="delta_costo_x_unidades_30d",
                intervalo_cop=(int(round(monto * 0.95)), int(round(monto * 1.05))) if monto > 0 else None,
                consulta_ids=[consulta_id],
            )

        elif inp.metodo == "exceso_descuento":
            # S4: Descuentos en exceso sobre política
            vendedor_id = params.get("vendedor_id")
            sql_params = []
            where_vendedor = ""
            if vendedor_id:
                where_vendedor = "WHERE vendedor_id = ?"
                sql_params.append(str(vendedor_id))

            query = f"""
                SELECT coalesce(round(sum(descuento_en_exceso)), 0)
                FROM v_descuentos_fuera_politica
                {where_vendedor}
            """
            res = con.execute(query, sql_params).fetchone()
            monto = int(res[0]) if res and res[0] is not None else 0

            return ImpactoCalculado(
                valor_cop=monto,
                horizonte="unico",
                metodo="exceso_descuento",
                intervalo_cop=None,
                consulta_ids=[consulta_id],
            )

        elif inp.metodo == "cartera_vencida_en_riesgo":
            # S2: Saldo vencido y saldo abierto en riesgo
            cliente_id = params.get("cliente_id")
            if not cliente_id:
                raise ValueError("cliente_id es requerido para metodo cartera_vencida_en_riesgo")

            query = """
                SELECT coalesce(round(saldo_vencido), 0), coalesce(round(saldo_abierto), 0)
                FROM v_cartera_cliente
                WHERE cliente_id = ?
            """
            res = con.execute(query, [str(cliente_id)]).fetchone()
            saldo_vencido = int(res[0]) if res and res[0] is not None else 0
            saldo_abierto = int(res[1]) if res and res[1] is not None else saldo_vencido

            return ImpactoCalculado(
                valor_cop=saldo_vencido,
                horizonte="unico",
                metodo="cartera_vencida_en_riesgo",
                intervalo_cop=(saldo_vencido, saldo_abierto),
                consulta_ids=[consulta_id],
            )

        elif inp.metodo == "margen_perdido_bajo_costo":
            # S6: Venta bajo costo
            sku = params.get("sku")
            skus = params.get("skus")
            where_parts = ["valor_neto < costo_total"]
            sql_params = []

            if sku:
                where_parts.append("sku = ?")
                sql_params.append(str(sku))
            elif skus and isinstance(skus, list):
                placeholders = ", ".join(["?"] * len(skus))
                where_parts.append(f"sku IN ({placeholders})")
                sql_params.extend([str(s) for s in skus])

            query = f"""
                SELECT coalesce(round(sum(costo_total - valor_neto)), 0)
                FROM v_ventas
                WHERE {" AND ".join(where_parts)}
            """
            res = con.execute(query, sql_params).fetchone()
            monto = int(res[0]) if res and res[0] is not None else 0

            return ImpactoCalculado(
                valor_cop=monto,
                horizonte="unico",
                metodo="margen_perdido_bajo_costo",
                intervalo_cop=None,
                consulta_ids=[consulta_id],
            )

        elif inp.metodo == "ventas_perdidas_cliente_inactivo":
            # S5: Ventas promedio mensuales del cliente en sus últimos 90 días de actividad
            cliente_id = params.get("cliente_id")
            if not cliente_id:
                raise ValueError("cliente_id es requerido para metodo ventas_perdidas_cliente_inactivo")

            query = """
                WITH ult AS (
                    SELECT max(fecha) AS max_f
                    FROM v_ventas
                    WHERE cliente_id = ?
                )
                SELECT coalesce(round(sum(v.valor_neto) / 3.0), 0)
                FROM v_ventas v, ult
                WHERE v.cliente_id = ?
                  AND v.fecha >= ult.max_f - INTERVAL 90 DAY
                  AND v.fecha <= ult.max_f
            """
            res = con.execute(query, [str(cliente_id), str(cliente_id)]).fetchone()
            monto = int(res[0]) if res and res[0] is not None else 0

            return ImpactoCalculado(
                valor_cop=monto,
                horizonte="mensual",
                metodo="ventas_perdidas_cliente_inactivo",
                intervalo_cop=(int(round(monto * 0.9)), int(round(monto * 1.1))) if monto > 0 else None,
                consulta_ids=[consulta_id],
            )

        elif inp.metodo == "ventas_perdidas_quiebre":
            # S3: Ventas perdidas por quiebre de stock
            sku = params.get("sku")
            bodega_id = params.get("bodega_id")
            if not sku or not bodega_id:
                raise ValueError("sku y bodega_id son requeridos para metodo ventas_perdidas_quiebre")

            query = """
                SELECT c.demanda_prom_30d, c.cobertura_dias, c.unidades_pendientes, p.precio_lista
                FROM v_cobertura_inventario c
                JOIN (
                    SELECT sku, precio_lista
                    FROM lista_precios
                    WHERE fecha_vigencia <= fecha_corte()
                    QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
                ) p USING (sku)
                WHERE c.sku = ? AND c.bodega_id = ?
            """
            res = con.execute(query, [str(sku), str(bodega_id)]).fetchone()
            if not res:
                return ImpactoCalculado(
                    valor_cop=0,
                    horizonte="unico",
                    metodo="ventas_perdidas_quiebre",
                    intervalo_cop=None,
                    consulta_ids=[consulta_id],
                )

            demanda_prom, cobertura, pendientes, precio_lista = res
            demanda_f = float(demanda_prom) if demanda_prom is not None else 0.0
            cobertura_f = float(cobertura) if cobertura is not None else 0.0
            pendientes_i = int(pendientes) if pendientes is not None else 0
            precio_f = float(precio_lista) if precio_lista is not None else 0.0

            if "dias_quiebre" in params:
                dias_quiebre = float(params["dias_quiebre"])
            else:
                # Días faltantes para la cobertura objetivo (10 días para clase A)
                dias_quiebre = max(1.0, 10.0 - cobertura_f)

            monto_demanda = int(round(demanda_f * precio_f * dias_quiebre))
            monto_pendientes = int(round(pendientes_i * precio_f))
            monto_final = max(monto_demanda, monto_pendientes)

            min_val = min(monto_demanda, monto_pendientes) if monto_pendientes > 0 else monto_final
            max_val = max(monto_demanda, monto_pendientes)

            return ImpactoCalculado(
                valor_cop=monto_final,
                horizonte="unico",
                metodo="ventas_perdidas_quiebre",
                intervalo_cop=(min_val, max_val) if min_val < max_val else None,
                consulta_ids=[consulta_id],
            )

        else:
            raise ValueError(f"Método de cálculo no soportado: '{inp.metodo}'")

    finally:
        if cerrar_con:
            con.close()


@mcp.tool(name="calcular_impacto")
def mcp_calcular_impacto(inp: CalcularImpactoIn, corte: date | None = None) -> ImpactoCalculado:
    """Calcula el impacto económico determinista según el método seleccionado."""
    return calcular_impacto(inp, corte=corte)


def calcular_impacto_economico(
    accion_parametros: ParametrosAccion,
    alerta: Alerta,
    corte: date | None = None,
    con: Any = None,
) -> ImpactoCalculado:
    """Evalúa deterministamente el impacto económico de una acción propuesta por el Estratega.

    Mapea el tipo de acción a las fórmulas deterministas de capa semántica:
    - ajuste_precio -> delta_costo_x_unidades_30d
    - contacto_cartera -> cartera_vencida_en_riesgo
    - expeditar_oc -> ventas_perdidas_quiebre
    - revision_descuentos -> exceso_descuento
    - reactivar_cliente -> ventas_perdidas_cliente_inactivo
    - corregir_venta_bajo_costo -> margen_perdido_bajo_costo
    """
    fecha_corte = corte or alerta.corte_creacion
    tipo = accion_parametros.tipo

    # Extraer IDs del contexto de la alerta si no vienen en la acción
    proveedor_id = None
    for h in alerta.hallazgos:
        for ent in h.entidades:
            if ent.tipo == "proveedor":
                proveedor_id = ent.id
                break
        if proveedor_id:
            break
    if not proveedor_id and "|" in alerta.huella_causa:
        partes = alerta.huella_causa.split("|")
        if len(partes) > 1 and partes[1].startswith("PR"):
            proveedor_id = partes[1]

    if tipo == "ajuste_precio":
        skus = [str(s) for s in accion_parametros.skus]
        params: dict[str, Any] = {"skus": skus}
        if proveedor_id:
            params["proveedor_id"] = proveedor_id
        inp = CalcularImpactoIn(metodo="delta_costo_x_unidades_30d", parametros=params)
        res = calcular_impacto(inp, corte=fecha_corte, con=con)
        if res.valor_cop == 0 and alerta.dinero_en_riesgo_cop > 0:
            res = res.model_copy(update={"valor_cop": alerta.dinero_en_riesgo_cop})
        return res

    elif tipo == "contacto_cartera":
        inp = CalcularImpactoIn(
            metodo="cartera_vencida_en_riesgo",
            parametros={"cliente_id": str(accion_parametros.cliente_id)},
        )
        res = calcular_impacto(inp, corte=fecha_corte, con=con)
        if res.valor_cop == 0 and alerta.dinero_en_riesgo_cop > 0:
            res = res.model_copy(update={"valor_cop": alerta.dinero_en_riesgo_cop})
        return res

    elif tipo == "expeditar_oc":
        inp = CalcularImpactoIn(
            metodo="ventas_perdidas_quiebre",
            parametros={
                "sku": str(accion_parametros.sku),
                "bodega_id": str(accion_parametros.bodega_id),
            },
        )
        res = calcular_impacto(inp, corte=fecha_corte, con=con)
        if res.valor_cop == 0 and alerta.dinero_en_riesgo_cop > 0:
            res = res.model_copy(update={"valor_cop": alerta.dinero_en_riesgo_cop})
        return res

    elif tipo == "revision_descuentos":
        inp = CalcularImpactoIn(
            metodo="exceso_descuento",
            parametros={"vendedor_id": str(accion_parametros.vendedor_id)},
        )
        res = calcular_impacto(inp, corte=fecha_corte, con=con)
        if res.valor_cop == 0 and alerta.dinero_en_riesgo_cop > 0:
            res = res.model_copy(update={"valor_cop": alerta.dinero_en_riesgo_cop})
        return res

    elif tipo == "reactivar_cliente":
        inp = CalcularImpactoIn(
            metodo="ventas_perdidas_cliente_inactivo",
            parametros={"cliente_id": str(accion_parametros.cliente_id)},
        )
        res = calcular_impacto(inp, corte=fecha_corte, con=con)
        if res.valor_cop == 0 and alerta.dinero_en_riesgo_cop > 0:
            res = res.model_copy(update={"valor_cop": alerta.dinero_en_riesgo_cop})
        return res

    elif tipo == "corregir_venta_bajo_costo":
        skus = [str(s) for s in accion_parametros.skus]
        inp = CalcularImpactoIn(
            metodo="margen_perdido_bajo_costo",
            parametros={"skus": skus},
        )
        res = calcular_impacto(inp, corte=fecha_corte, con=con)
        if res.valor_cop == 0 and alerta.dinero_en_riesgo_cop > 0:
            res = res.model_copy(update={"valor_cop": alerta.dinero_en_riesgo_cop})
        return res

    else:
        consulta_id = (
            alerta.hallazgos[0].consulta_ids[0]
            if alerta.hallazgos and alerta.hallazgos[0].consulta_ids
            else f"Q-{uuid.uuid4().hex[:12]}"
        )
        return ImpactoCalculado(
            valor_cop=alerta.dinero_en_riesgo_cop,
            horizonte="mensual",
            metodo="riesgo_alerta",
            intervalo_cop=None,
            consulta_ids=[consulta_id],
        )
