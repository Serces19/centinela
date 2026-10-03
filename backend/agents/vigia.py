# backend/agents/vigia.py
"""Agente Vigía determinista de Centinela (sin LLM).

Monitorea continuamente la capa semántica sobre DuckDB para detectar desviaciones
operacionales y financieras según las políticas del negocio (OPE-POL-007, FIN-POL-004, COM-POL-002):
- S1 (Margen / Costo): Aumento de costo de proveedor > 5% y caída de margen semanal por línea.
- S2 (Cartera / Mora): Días de mora > 15 días o saldo abierto > cupo de crédito (FIN-POL-004).
- S2 (Días de pago): Aumento > 50% vs promedio histórico del cliente.
- S3 (Cobertura / Quiebre): Cobertura < 10d en clase A; crítico < 5d con pedidos pendientes.
- S4 (Descuentos): Descuentos fuera de política por vendedor (2 semanas consecutivas).
- S5 (Inactividad): Cliente con >= 10 pedidos que supera 3x su intervalo de compra habitual.
- S6 (Venta bajo costo): Líneas con valor neto inferior al costo unitario total.

Incluye:
- Estadística robusta de apoyo: z-score robusto basado en MAD (Median Absolute Deviation).
- Deduplicación y agrupación por `huella_causa = '{kpi}|{entidad_raiz}'`.
- Priorización estricta por `dinero_en_riesgo_cop` descendente.
"""

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import statistics
import time
import uuid
from typing import Any

from contracts.alertas import Alerta, Hallazgo
from contracts.base import (
    AlertaId,
    ConsultaId,
    EntidadRef,
    EstadoAlerta,
    Kpi,
    Pesos,
    SCHEMA_VERSION,
    Severidad,
    TipoEntidad,
)
from contracts.herramientas import CalcularImpactoIn
from semantic.db import FECHA_CORTE_DEFECTO, get_duckdb_connection
from services.telemetry import (
    emitir_alertas_generadas,
    emitir_pipeline_latencia,
    log_evento,
)
from tools.impacto import calcular_impacto

# Orden de precedencia de severidad
_SEVERIDAD_RANK = {
    Severidad.CRITICA: 4,
    Severidad.ALTA: 3,
    Severidad.MEDIA: 2,
    Severidad.BAJA: 1,
}


def calcular_zscore_robusto(valores: list[float], valor_actual: float) -> float:
    """Calcula el z-score robusto usando MAD (Median Absolute Deviation).

    Fórmula: Z = (valor_actual - mediana) / (1.4826 * MAD)
    Si MAD es cero, usa desviación estándar clásica como fallback.
    """
    if not valores:
        return 0.0
    mediana = float(statistics.median(valores))
    desviaciones = [abs(x - mediana) for x in valores]
    mad = float(statistics.median(desviaciones))
    if mad == 0.0:
        stdev = statistics.stdev(valores) if len(valores) > 1 else 0.0
        return (valor_actual - mediana) / stdev if stdev > 0.0 else 0.0
    return (valor_actual - mediana) / (1.4826 * mad)


def analizar_caida_margen_linea(
    linea: str,
    corte: date,
    con: Any = None,
) -> tuple[float, float, float]:
    """Evalúa la serie histórica semanal de margen de una línea hasta la fecha de corte.

    Retorna: (margen_semana_reciente, mediana_historica, z_score_robusto)
    """
    cerrar_con = False
    if con is None:
        con = get_duckdb_connection(corte)
        cerrar_con = True

    try:
        rows = con.execute("""
            SELECT semana, margen_pct
            FROM v_margen_semanal_linea
            WHERE linea = ?
            ORDER BY semana ASC
        """, [linea]).fetchall()

        if not rows:
            return 0.0, 0.0, 0.0

        margenes = [float(r[1]) for r in rows if r[1] is not None]
        if not margenes:
            return 0.0, 0.0, 0.0

        valor_reciente = margenes[-1]
        historico = margenes[:-1] if len(margenes) > 1 else margenes
        mediana = float(statistics.median(historico))
        z_score = calcular_zscore_robusto(historico, valor_reciente)

        return valor_reciente, mediana, z_score
    finally:
        if cerrar_con:
            con.close()


def _detectar_s1_costo_proveedor(con: Any, corte: date) -> list[Hallazgo]:
    """Detecta aumentos de costo de proveedor > 5% (OPE-POL-007) y caída de margen."""
    hallazgos: list[Hallazgo] = []
    consulta_id = f"Q-{uuid.uuid4().hex[:12]}"

    query = """
        WITH costos AS (
            SELECT sku, proveedor_id, costo_unitario, fecha_vigencia,
                   lag(costo_unitario) OVER (PARTITION BY sku ORDER BY fecha_vigencia) AS costo_anterior
            FROM costos_proveedor
            WHERE fecha_vigencia <= fecha_corte()
        ),
        saltos_recientes AS (
            SELECT sku, proveedor_id, costo_unitario, costo_anterior, fecha_vigencia,
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
        SELECT u.sku, u.proveedor_id, u.fecha_vigencia, u.costo_unitario, u.costo_anterior,
               u.delta_costo, u.pct_incremento, coalesce(d.unidades_30d, 0) AS unidades_30d,
               round(u.delta_costo * coalesce(d.unidades_30d, 0)) AS impacto_sku
        FROM saltos_recientes u
        LEFT JOIN dem_30d d USING (sku)
        ORDER BY impacto_sku DESC
    """
    rows = con.execute(query).fetchall()

    for r in rows:
        sku, proveedor_id, fecha_vigencia, costo_u, costo_ant, delta, pct_inc, unds_30d, impacto_sku = r
        monto_riesgo = int(impacto_sku) if impacto_sku is not None else 0

        h = Hallazgo(
            hallazgo_id=f"H-{uuid.uuid4().hex[:8]}",
            kpi=Kpi.MARGEN,
            regla="OPE-POL-007/costo+5%",
            severidad=Severidad.CRITICA if monto_riesgo > 10_000_000 else Severidad.ALTA,
            entidades=[
                EntidadRef(tipo=TipoEntidad.PROVEEDOR, id=str(proveedor_id)),
                EntidadRef(tipo=TipoEntidad.SKU, id=str(sku)),
            ],
            valor_observado=round(float(pct_inc) * 100.0, 2),
            umbral=5.0,
            corte=corte,
            dinero_en_riesgo_cop=monto_riesgo,
            consulta_ids=[consulta_id],
            huella_causa=f"costo|{proveedor_id}",
        )
        hallazgos.append(h)

    return hallazgos


def _detectar_s2_cartera_cliente(con: Any, corte: date) -> list[Hallazgo]:
    """Detecta mora vencida > 15 días o superación de cupo de crédito (FIN-POL-004)."""
    hallazgos: list[Hallazgo] = []
    consulta_id = f"Q-{uuid.uuid4().hex[:12]}"

    query = """
        SELECT cliente_id, cupo_credito, saldo_abierto, saldo_vencido, max_dias_vencido, dias_pago_prom_120d
        FROM v_cartera_cliente
        WHERE max_dias_vencido > 15 OR saldo_abierto > cupo_credito
        ORDER BY saldo_vencido DESC
    """
    rows = con.execute(query).fetchall()

    for r in rows:
        cliente_id, cupo, abierto, vencido, dias_vencido, dias_pago_120d = r
        dias_v = int(dias_vencido) if dias_vencido is not None else 0
        monto_vencido = int(round(vencido)) if vencido is not None else 0
        monto_abierto = int(round(abierto)) if abierto is not None else 0

        # Escalamiento FIN-POL-004:
        # > 60 días: bloqueo de despachos (CRITICA)
        # 31-60 días: solo contado (ALTA)
        # 16-30 días: llamada + alerta (MEDIA)
        # <= 15 días pero cupo excedido: ALTA
        if dias_v > 60:
            sev = Severidad.CRITICA
        elif dias_v > 30:
            sev = Severidad.ALTA
        elif dias_v > 15:
            sev = Severidad.MEDIA
        else:
            sev = Severidad.ALTA  # saldo_abierto > cupo

        h = Hallazgo(
            hallazgo_id=f"H-{uuid.uuid4().hex[:8]}",
            kpi=Kpi.SALDO_VENCIDO,
            regla="FIN-POL-004/mora>15d",
            severidad=sev,
            entidades=[EntidadRef(tipo=TipoEntidad.CLIENTE, id=str(cliente_id))],
            valor_observado=float(dias_v),
            umbral=15.0,
            corte=corte,
            dinero_en_riesgo_cop=monto_vencido if monto_vencido > 0 else monto_abierto,
            consulta_ids=[consulta_id],
            huella_causa=f"saldo_vencido|{cliente_id}",
        )
        hallazgos.append(h)

    return hallazgos


def _detectar_s2_dias_pago(con: Any, corte: date) -> list[Hallazgo]:
    """Detecta aumento > 50% en días de pago promedio vs histórico del cliente (FIN-POL-004 §4)."""
    hallazgos: list[Hallazgo] = []
    consulta_id = f"Q-{uuid.uuid4().hex[:12]}"

    # Comparamos el último mes con el promedio histórico por cliente
    query = """
        WITH ult_mes AS (
            SELECT cliente_id, mes_factura, dias_pago_prom
            FROM v_dias_pago_mensual
            QUALIFY row_number() OVER (PARTITION BY cliente_id ORDER BY mes_factura DESC) = 1
        ),
        hist AS (
            SELECT cliente_id, avg(dias_pago_prom) AS dias_pago_hist
            FROM v_dias_pago_mensual
            GROUP BY cliente_id
        ),
        cart AS (
            SELECT cliente_id, saldo_vencido
            FROM v_cartera_cliente
        )
        SELECT u.cliente_id, u.dias_pago_prom, h.dias_pago_hist,
               (u.dias_pago_prom - h.dias_pago_hist) / nullif(h.dias_pago_hist, 0) AS incremento_pct,
               coalesce(round(c.saldo_vencido), 0) AS saldo_vencido
        FROM ult_mes u
        JOIN hist h USING (cliente_id)
        JOIN cart c USING (cliente_id)
        WHERE (u.dias_pago_prom - h.dias_pago_hist) / nullif(h.dias_pago_hist, 0) > 0.50
        ORDER BY saldo_vencido DESC
    """
    rows = con.execute(query).fetchall()

    for r in rows:
        cliente_id, dias_recientes, dias_hist, inc_pct, saldo_venc = r
        recientes_f = float(dias_recientes) if dias_recientes is not None else 0.0
        hist_f = float(dias_hist) if dias_hist is not None else 0.0
        saldo_v = int(saldo_venc) if saldo_venc is not None else 0

        h = Hallazgo(
            hallazgo_id=f"H-{uuid.uuid4().hex[:8]}",
            kpi=Kpi.DIAS_PAGO,
            regla="FIN-POL-004/dias_pago+50%",
            severidad=Severidad.MEDIA,
            entidades=[EntidadRef(tipo=TipoEntidad.CLIENTE, id=str(cliente_id))],
            valor_observado=recientes_f,
            umbral=round(hist_f * 1.5, 1),
            corte=corte,
            dinero_en_riesgo_cop=saldo_v,
            consulta_ids=[consulta_id],
            huella_causa=f"saldo_vencido|{cliente_id}",
        )
        hallazgos.append(h)

    return hallazgos


def _detectar_s3_cobertura_inventario(con: Any, corte: date) -> list[Hallazgo]:
    """Detecta quiebre inminente de inventario (OPE-POL-007): cobertura < 10d (A) y crítico < 5d."""
    hallazgos: list[Hallazgo] = []
    consulta_id = f"Q-{uuid.uuid4().hex[:12]}"

    # Priorizamos casos críticos: cobertura < 5 días con pedidos pendientes o clase A < 10 días
    query = """
        SELECT c.sku, c.bodega_id, c.clase_abc, c.cobertura_dias, c.demanda_prom_30d,
               c.unidades_pendientes, p.precio_lista
        FROM v_cobertura_inventario c
        JOIN (
            SELECT sku, precio_lista
            FROM lista_precios
            WHERE fecha_vigencia <= fecha_corte()
            QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
        ) p USING (sku)
        WHERE (c.cobertura_dias < 5.0 AND c.unidades_pendientes > 0)
           OR (c.clase_abc = 'A' AND c.cobertura_dias < 10.0 AND c.unidades_pendientes > 0)
        ORDER BY c.cobertura_dias ASC
    """
    rows = con.execute(query).fetchall()

    for r in rows:
        sku, bodega_id, clase_abc, cobertura, dem_prom, pendientes, precio_l = r
        cobertura_f = float(cobertura) if cobertura is not None else 0.0
        dem_f = float(dem_prom) if dem_prom is not None else 0.0
        pend_i = int(pendientes) if pendientes is not None else 0
        precio_f = float(precio_l) if precio_l is not None else 0.0

        es_critico = cobertura_f < 5.0 and pend_i > 0
        dias_quiebre = max(1.0, 10.0 - cobertura_f)
        dinero_riesgo = int(round(max(dem_f * precio_f * dias_quiebre, pend_i * precio_f)))

        h = Hallazgo(
            hallazgo_id=f"H-{uuid.uuid4().hex[:8]}",
            kpi=Kpi.COBERTURA,
            regla="OPE-POL-007/cobertura_critica" if es_critico else "OPE-POL-007/cobertura<10d",
            severidad=Severidad.CRITICA if es_critico else Severidad.ALTA,
            entidades=[
                EntidadRef(tipo=TipoEntidad.SKU, id=str(sku)),
                EntidadRef(tipo=TipoEntidad.BODEGA, id=str(bodega_id)),
            ],
            valor_observado=cobertura_f,
            umbral=5.0 if es_critico else 10.0,
            corte=corte,
            dinero_en_riesgo_cop=dinero_riesgo,
            consulta_ids=[consulta_id],
            huella_causa=f"cobertura_dias|{sku}",
        )
        hallazgos.append(h)

    return hallazgos


def _detectar_s4_descuentos_fuera_politica(con: Any, corte: date) -> list[Hallazgo]:
    """Detecta descuentos fuera de política agrupados por vendedor (COM-POL-002 §5)."""
    hallazgos: list[Hallazgo] = []
    consulta_id = f"Q-{uuid.uuid4().hex[:12]}"

    query = """
        SELECT vendedor_id, count(*) AS lineas, count(DISTINCT date_trunc('week', fecha)) AS semanas,
               round(sum(descuento_en_exceso)) AS total_exceso
        FROM v_descuentos_fuera_politica
        GROUP BY vendedor_id
        HAVING count(DISTINCT date_trunc('week', fecha)) >= 2 OR count(*) >= 10
        ORDER BY total_exceso DESC
    """
    rows = con.execute(query).fetchall()

    for r in rows:
        vendedor_id, lineas, semanas, total_exceso = r
        exceso_int = int(total_exceso) if total_exceso is not None else 0

        h = Hallazgo(
            hallazgo_id=f"H-{uuid.uuid4().hex[:8]}",
            kpi=Kpi.DESCUENTO_EXCESO,
            regla="COM-POL-002/descuento_exceso_2sem",
            severidad=Severidad.ALTA,
            entidades=[EntidadRef(tipo=TipoEntidad.VENDEDOR, id=str(vendedor_id))],
            valor_observado=float(exceso_int),
            umbral=0.0,
            corte=corte,
            dinero_en_riesgo_cop=exceso_int,
            consulta_ids=[consulta_id],
            huella_causa=f"descuento_en_exceso|{vendedor_id}",
        )
        hallazgos.append(h)

    return hallazgos


def _detectar_s5_inactividad_cliente(con: Any, corte: date) -> list[Hallazgo]:
    """Detecta clientes habituales (pedidos >= 10) inactivos > 3x su intervalo regular."""
    hallazgos: list[Hallazgo] = []
    consulta_id = f"Q-{uuid.uuid4().hex[:12]}"

    # Calculamos también el dinero en riesgo (ventas promedio mensuales en últimos 90d activos)
    query = """
        WITH inactivos AS (
            SELECT cliente_id, pedidos, ultima_compra, veces_intervalo_habitual
            FROM v_actividad_cliente
            WHERE veces_intervalo_habitual > 3.0 AND pedidos >= 10
        ),
        ventas_90d AS (
            SELECT i.cliente_id,
                   coalesce(round(sum(v.valor_neto) / 3.0), 0) AS ventas_prom_mensual
            FROM inactivos i
            JOIN v_ventas v ON v.cliente_id = i.cliente_id
                           AND v.fecha >= i.ultima_compra - INTERVAL 90 DAY
                           AND v.fecha <= i.ultima_compra
            GROUP BY i.cliente_id
        )
        SELECT i.cliente_id, i.pedidos, i.veces_intervalo_habitual, coalesce(v.ventas_prom_mensual, 0) AS riesgo_mensual
        FROM inactivos i
        LEFT JOIN ventas_90d v USING (cliente_id)
        ORDER BY i.veces_intervalo_habitual DESC
    """
    rows = con.execute(query).fetchall()

    for r in rows:
        cliente_id, pedidos, veces_int, riesgo_mensual = r
        veces_f = float(veces_int) if veces_int is not None else 0.0
        riesgo_int = int(riesgo_mensual) if riesgo_mensual is not None else 0

        h = Hallazgo(
            hallazgo_id=f"H-{uuid.uuid4().hex[:8]}",
            kpi=Kpi.INTERVALO_COMPRA,
            regla="COM-POL-001/inactividad>3x",
            severidad=Severidad.CRITICA if riesgo_int > 20_000_000 else Severidad.ALTA,
            entidades=[EntidadRef(tipo=TipoEntidad.CLIENTE, id=str(cliente_id))],
            valor_observado=veces_f,
            umbral=3.0,
            corte=corte,
            dinero_en_riesgo_cop=riesgo_int,
            consulta_ids=[consulta_id],
            huella_causa=f"veces_intervalo_habitual|{cliente_id}",
        )
        hallazgos.append(h)

    return hallazgos


def _detectar_s6_venta_bajo_costo(con: Any, corte: date) -> list[Hallazgo]:
    """Detecta ventas bajo costo unitario (COM-POL-002 §4)."""
    hallazgos: list[Hallazgo] = []
    consulta_id = f"Q-{uuid.uuid4().hex[:12]}"

    # Agrupamos por SKU principal afectado
    query = """
        SELECT sku, count(*) AS lineas, round(sum(costo_total - valor_neto)) AS perdida_directa
        FROM v_ventas
        WHERE valor_neto < costo_total
        GROUP BY sku
        HAVING sum(costo_total - valor_neto) > 500000
        ORDER BY perdida_directa DESC
    """
    rows = con.execute(query).fetchall()

    for r in rows:
        sku, lineas, perdida = r
        perdida_int = int(perdida) if perdida is not None else 0

        h = Hallazgo(
            hallazgo_id=f"H-{uuid.uuid4().hex[:8]}",
            kpi=Kpi.VENTA_BAJO_COSTO,
            regla="COM-POL-002/venta_bajo_costo",
            severidad=Severidad.ALTA,
            entidades=[EntidadRef(tipo=TipoEntidad.SKU, id=str(sku))],
            valor_observado=float(perdida_int),
            umbral=0.0,
            corte=corte,
            dinero_en_riesgo_cop=perdida_int,
            consulta_ids=[consulta_id],
            huella_causa=f"venta_bajo_costo|{sku}",
        )
        hallazgos.append(h)

    return hallazgos


def detectar_hallazgos(corte: date, con: Any = None) -> list[Hallazgo]:
    """Ejecuta deterministamente todas las reglas de los 6 KPIs + S6 a la fecha de corte.

    Args:
        corte: Fecha de corte del reloj simulado.
        con: Conexión DuckDB opcional reutilizable.
    """
    cerrar_con = False
    if con is None:
        con = get_duckdb_connection(corte)
        cerrar_con = True

    try:
        hallazgos: list[Hallazgo] = []
        hallazgos.extend(_detectar_s1_costo_proveedor(con, corte))
        hallazgos.extend(_detectar_s2_cartera_cliente(con, corte))
        hallazgos.extend(_detectar_s2_dias_pago(con, corte))
        hallazgos.extend(_detectar_s3_cobertura_inventario(con, corte))
        hallazgos.extend(_detectar_s4_descuentos_fuera_politica(con, corte))
        hallazgos.extend(_detectar_s5_inactividad_cliente(con, corte))
        hallazgos.extend(_detectar_s6_venta_bajo_costo(con, corte))
        return hallazgos
    finally:
        if cerrar_con:
            con.close()


def generar_alertas(corte: date, con: Any = None) -> list[Alerta]:
    """Genera y deduplica alertas a partir de los hallazgos deterministas del Vigía.

    - Agrupa hallazgos bajo la misma `huella_causa = '{kpi}|{entidad_raiz}'`.
    - Asigna `alerta_id = ALR-<yyyymmdd>-<6 hex>`.
    - Determina la severidad máxima del grupo.
    - Suma o consolida el dinero en riesgo total de la causa.
    - Ordena las alertas por `dinero_en_riesgo_cop` DESCENDENTE.
    - Emite métricas CloudWatch EMF (PipelineLatenciaMs y AlertasGeneradas).
    """
    inicio = time.perf_counter()
    hallazgos = detectar_hallazgos(corte, con=con)
    if not hallazgos:
        latencia_ms = (time.perf_counter() - inicio) * 1000.0
        emitir_pipeline_latencia("vigia", latencia_ms)
        log_evento("INFO", "vigia.cero_hallazgos", agente="vigia", corte=corte.isoformat(), latencia_ms=round(latencia_ms, 2))
        return []

    grupos: dict[str, list[Hallazgo]] = defaultdict(list)
    for h in hallazgos:
        grupos[h.huella_causa].append(h)

    alertas: list[Alerta] = []
    fecha_str = corte.strftime("%Y%m%d")

    for huella, items in grupos.items():
        # Severidad máxima en el grupo
        max_sev = max(items, key=lambda x: _SEVERIDAD_RANK.get(x.severidad, 0)).severidad

        # Para dinero en riesgo de la alerta:
        # Si es costo de proveedor (S1), se suman los SKUs afectados de ese proveedor.
        # Si es cartera (S2), tomamos el máximo entre saldo vencido y alertas de días de pago.
        if huella.startswith("saldo_vencido|"):
            monto_alerta = max(x.dinero_en_riesgo_cop for x in items)
        else:
            monto_alerta = sum(x.dinero_en_riesgo_cop for x in items)

        hash_hex = hashlib.md5(f"{corte.isoformat()}|{huella}".encode("utf-8")).hexdigest()[:6]
        alerta_id = f"ALR-{fecha_str}-{hash_hex}"

        alerta = Alerta(
            schema_version=SCHEMA_VERSION,
            alerta_id=alerta_id,
            estado=EstadoAlerta.NUEVA,
            huella_causa=huella,
            hallazgos=items,
            severidad=max_sev,
            dinero_en_riesgo_cop=monto_alerta,
            corte_creacion=corte,
            creada_en=datetime.now(timezone.utc),
            version=1,
        )
        alertas.append(alerta)
        kpi_nombre = items[0].kpi.value if items else huella.split("|")[0]
        emitir_alertas_generadas(kpi=kpi_nombre, severidad=alerta.severidad.value, count=1)

    # Ordenar por dinero en riesgo descendente (prioridad comercial/financiera)
    alertas.sort(key=lambda a: a.dinero_en_riesgo_cop, reverse=True)

    latencia_ms = (time.perf_counter() - inicio) * 1000.0
    emitir_pipeline_latencia("vigia", latencia_ms)
    log_evento(
        "INFO",
        "vigia.alertas_generadas",
        agente="vigia",
        corte=corte.isoformat(),
        total_alertas=len(alertas),
        latencia_ms=round(latencia_ms, 2),
    )
    return alertas
