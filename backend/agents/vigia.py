# backend/agents/vigia.py
"""Agente Vigía determinista de Centinela (sin LLM).

Vigila los 6 KPIs sobre la capa semántica (DuckDB) con las reglas de política y, como apoyo, estadística robusta:

- Margen (KPI 1): alza de costo de proveedor > umbral (OPE-POL-007 §4) y caída de margen semanal por línea
  frente a las 8 semanas previas o margen bajo el mínimo de la línea.
- Saldo vencido (KPI 2): días vencidos > umbral o saldo abierto > cupo (FIN-POL-004).
- Días de pago (KPI 3): aumento > umbral frente al histórico del cliente (FIN-POL-004 §5).
- Cobertura (KPI 4): clase A bajo el mínimo o cobertura crítica, con pedidos pendientes (OPE-POL-007 §2).
- Descuento en exceso (KPI 5): líneas sobre el tope sin aprobación, por vendedor (COM-POL-002 §5).
- Intervalo de compra (KPI 6): cliente habitual que supera N veces su intervalo (metricas.yaml).
- Venta bajo costo: línea con valor neto menor al costo (COM-POL-002 §4).

Cada regla ejecuta **una consulta registrada** (`ConsultaRegistrada`): todo hallazgo enlaza el SQL, el corte y el
hash del resultado que lo originó. Los umbrales vienen de `services.umbrales` (política + configuración).

Una causa = una alerta: los hallazgos se agrupan por `huella_causa` (`kpi|entidad raíz`). La caída de margen de una
línea se asocia a la causa de costo del proveedor cuando los SKU afectados pertenecen a esa línea.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import statistics
import time
from typing import Any

from contracts.alertas import Alerta, Hallazgo
from contracts.base import EntidadRef, EstadoAlerta, Kpi, SCHEMA_VERSION, Severidad, TipoEntidad
from semantic.db import get_duckdb_connection
from services.registro_consultas import ResultadoConsulta, ejecutar_registrada
from services.telemetry import emitir_alertas_generadas, emitir_pipeline_latencia, log_evento
from services.umbrales import Umbrales, cargar_umbrales

_SEVERIDAD_RANK = {Severidad.CRITICA: 4, Severidad.ALTA: 3, Severidad.MEDIA: 2, Severidad.BAJA: 1}


# -----------------------------------------------------------------------------
# Estadística robusta de apoyo
# -----------------------------------------------------------------------------
def calcular_zscore_robusto(valores: list[float], valor_actual: float) -> float:
    """Z robusto con MAD: (x - mediana) / (1,4826 * MAD). Si MAD = 0 usa la desviación estándar."""
    if not valores:
        return 0.0
    mediana = float(statistics.median(valores))
    mad = float(statistics.median([abs(x - mediana) for x in valores]))
    if mad == 0.0:
        stdev = statistics.stdev(valores) if len(valores) > 1 else 0.0
        return (valor_actual - mediana) / stdev if stdev > 0.0 else 0.0
    return (valor_actual - mediana) / (1.4826 * mad)


def analizar_caida_margen_linea(linea: str, corte: date, con: Any = None) -> tuple[float, float, float]:
    """Serie semanal de margen de una línea hasta el corte: (margen reciente, mediana histórica, z robusto).

    Segunda señal, de apoyo a la regla de política: marca la caída aunque el umbral configurado no se alcance.
    """
    cerrar_con = con is None
    if con is None:
        con = get_duckdb_connection(corte)
    try:
        filas = con.execute(
            "SELECT semana, margen_pct FROM v_margen_semanal_linea WHERE linea = ? ORDER BY semana ASC", [linea]
        ).fetchall()
        margenes = [float(f[1]) for f in filas if f[1] is not None]
        if not margenes:
            return 0.0, 0.0, 0.0
        reciente = margenes[-1]
        historico = margenes[:-1] if len(margenes) > 1 else margenes
        return reciente, float(statistics.median(historico)), calcular_zscore_robusto(historico, reciente)
    finally:
        if cerrar_con:
            con.close()


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
def _hid(*partes: Any) -> str:
    return "H-" + hashlib.sha1("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()[:8]


def _sev_por_monto(monto: int, critica_desde: int) -> Severidad:
    return Severidad.CRITICA if monto > critica_desde else Severidad.ALTA


def _filas(res: ResultadoConsulta) -> list[dict[str, Any]]:
    return [dict(zip(res.columnas, fila)) for fila in res.filas]


def _q(con: Any, corte: date, sql: str, vista: str, descripcion: str, params: list[Any] | None = None) -> ResultadoConsulta:
    return ejecutar_registrada(con, sql, params, vista=vista, corte=corte, descripcion=descripcion)


# -----------------------------------------------------------------------------
# Reglas
# -----------------------------------------------------------------------------
def _detectar_costo_proveedor(con: Any, corte: date, u: Umbrales) -> list[Hallazgo]:
    """Alza de costo de proveedor por encima del umbral en los últimos 60 días (OPE-POL-007 §4)."""
    res = _q(
        con,
        corte,
        """
        WITH costos AS (
            SELECT sku, proveedor_id, costo_unitario, fecha_vigencia,
                   lag(costo_unitario) OVER (PARTITION BY sku ORDER BY fecha_vigencia) AS costo_anterior
            FROM costos_proveedor
            WHERE fecha_vigencia <= fecha_corte()
        ),
        saltos AS (
            SELECT sku, proveedor_id, costo_unitario, costo_anterior, fecha_vigencia,
                   (costo_unitario - costo_anterior) AS delta_costo,
                   (costo_unitario - costo_anterior) / nullif(costo_anterior, 0) AS pct_incremento
            FROM costos
            WHERE (costo_unitario - costo_anterior) / nullif(costo_anterior, 0) > ? / 100.0
              AND fecha_vigencia >= fecha_corte() - INTERVAL 60 DAY
            QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
        ),
        dem_30d AS (
            SELECT sku, sum(salidas) AS unidades_30d
            FROM inventario_diario
            WHERE fecha >= fecha_corte() - INTERVAL 30 DAY AND fecha < fecha_corte()
            GROUP BY sku
        )
        SELECT s.sku, s.proveedor_id, p.linea, s.fecha_vigencia, s.costo_anterior, s.costo_unitario,
               round(100 * s.pct_incremento, 2) AS pct_incremento, coalesce(d.unidades_30d, 0) AS unidades_30d,
               round(s.delta_costo * coalesce(d.unidades_30d, 0)) AS impacto_mensual
        FROM saltos s
        JOIN productos p USING (sku)
        LEFT JOIN dem_30d d USING (sku)
        ORDER BY impacto_mensual DESC
        """,
        "costos_proveedor",
        "Alzas de costo de proveedor mayores al umbral y su impacto mensual (unidades de 30 días por aumento de costo)",
        [u.costo_alza_pct],
    )
    hallazgos: list[Hallazgo] = []
    for r in _filas(res):
        monto = int(r["impacto_mensual"] or 0)
        hallazgos.append(
            Hallazgo(
                hallazgo_id=_hid("costo", r["proveedor_id"], r["sku"], corte),
                kpi=Kpi.MARGEN,
                regla="OPE-POL-007/costo_alza",
                severidad=_sev_por_monto(monto, 10_000_000),
                entidades=[
                    EntidadRef(tipo=TipoEntidad.PROVEEDOR, id=str(r["proveedor_id"])),
                    EntidadRef(tipo=TipoEntidad.SKU, id=str(r["sku"])),
                    EntidadRef(tipo=TipoEntidad.LINEA, id=str(r["linea"])),
                ],
                valor_observado=float(r["pct_incremento"]),
                umbral=u.costo_alza_pct,
                corte=corte,
                dinero_en_riesgo_cop=monto,
                consulta_ids=[res.consulta.consulta_id],
                huella_causa=f"costo|{r['proveedor_id']}",
            )
        )
    return hallazgos


def _detectar_margen_linea(con: Any, corte: date, u: Umbrales) -> list[Hallazgo]:
    """Caída de margen de una línea frente a las 8 semanas previas o margen bajo el mínimo (KPI 1)."""
    res = _q(
        con,
        corte,
        """
        WITH s AS (
            SELECT linea, semana, ventas, margen_pct,
                   row_number() OVER (PARTITION BY linea ORDER BY semana DESC) AS rn
            FROM v_margen_semanal_linea
            WHERE semana < date_trunc('week', fecha_corte())
        ),
        act AS (SELECT linea, avg(margen_pct) AS margen_actual, sum(ventas) AS ventas_3s FROM s WHERE rn <= 3 GROUP BY linea),
        base AS (SELECT linea, avg(margen_pct) AS margen_base FROM s WHERE rn BETWEEN 4 AND 11 GROUP BY linea)
        SELECT a.linea, round(a.margen_actual, 2) AS margen_actual, round(b.margen_base, 2) AS margen_base,
               round(a.margen_actual - b.margen_base, 2) AS delta_pp, r.margen_minimo_pct, round(a.ventas_3s) AS ventas_3s
        FROM act a
        JOIN base b USING (linea)
        JOIN ref_margen_minimo_linea r USING (linea)
        WHERE (b.margen_base - a.margen_actual) > ? OR a.margen_actual < r.margen_minimo_pct
        ORDER BY (b.margen_base - a.margen_actual) DESC
        """,
        "v_margen_semanal_linea",
        "Margen de las últimas 3 semanas completas por línea frente al promedio de las 8 semanas previas y al margen mínimo",
        [u.margen_caida_pp],
    )
    hallazgos: list[Hallazgo] = []
    for r in _filas(res):
        brecha = max(float(r["margen_base"]) - float(r["margen_actual"]), float(r["margen_minimo_pct"]) - float(r["margen_actual"]), 0.0)
        monto = int(round(float(r["ventas_3s"]) * (30.0 / 21.0) * brecha / 100.0))
        bajo_minimo = float(r["margen_actual"]) < float(r["margen_minimo_pct"])
        hallazgos.append(
            Hallazgo(
                hallazgo_id=_hid("margen", r["linea"], corte),
                kpi=Kpi.MARGEN,
                regla="OPE-POL-007/margen_minimo" if bajo_minimo else "metricas/margen_caida",
                severidad=_sev_por_monto(monto, 10_000_000),
                entidades=[EntidadRef(tipo=TipoEntidad.LINEA, id=str(r["linea"]))],
                valor_observado=float(r["margen_actual"]),
                umbral=float(r["margen_minimo_pct"]) if bajo_minimo else float(r["margen_base"]) - u.margen_caida_pp,
                corte=corte,
                dinero_en_riesgo_cop=monto,
                consulta_ids=[res.consulta.consulta_id],
                huella_causa=f"margen|{r['linea']}",
            )
        )
    return hallazgos


def _detectar_cartera(con: Any, corte: date, u: Umbrales) -> list[Hallazgo]:
    """Cartera vencida por encima del umbral de días o saldo abierto sobre el cupo (FIN-POL-004 §3-4)."""
    res = _q(
        con,
        corte,
        """
        SELECT cliente_id, cupo_credito, saldo_abierto, saldo_vencido, max_dias_vencido, dias_pago_prom_120d
        FROM v_cartera_cliente
        WHERE max_dias_vencido > ? OR saldo_abierto > cupo_credito
        ORDER BY saldo_vencido DESC
        """,
        "v_cartera_cliente",
        "Clientes con cartera vencida sobre el umbral de días o saldo abierto sobre el cupo de crédito",
        [u.dias_mora],
    )
    hallazgos: list[Hallazgo] = []
    for r in _filas(res):
        dias = int(r["max_dias_vencido"] or 0)
        vencido = int(round(r["saldo_vencido"] or 0))
        exceso_cupo = max(int(round((r["saldo_abierto"] or 0) - (r["cupo_credito"] or 0))), 0)
        # Escalamiento FIN-POL-004 §4: >60 bloqueo, 31-60 solo contado, 16-30 llamada, sobre cupo: alta
        if dias > 60:
            sev = Severidad.CRITICA
        elif dias > 30:
            sev = Severidad.ALTA
        elif dias > u.dias_mora:
            sev = Severidad.MEDIA
        else:
            sev = Severidad.ALTA
        hallazgos.append(
            Hallazgo(
                hallazgo_id=_hid("cartera", r["cliente_id"], corte),
                kpi=Kpi.SALDO_VENCIDO,
                regla="FIN-POL-004/mora" if dias > u.dias_mora else "FIN-POL-004/cupo_excedido",
                severidad=sev,
                entidades=[EntidadRef(tipo=TipoEntidad.CLIENTE, id=str(r["cliente_id"]))],
                valor_observado=float(dias),
                umbral=float(u.dias_mora),
                corte=corte,
                dinero_en_riesgo_cop=max(vencido, exceso_cupo),
                consulta_ids=[res.consulta.consulta_id],
                huella_causa=f"saldo_vencido|{r['cliente_id']}",
            )
        )
    return hallazgos


def _detectar_dias_pago(con: Any, corte: date, u: Umbrales) -> list[Hallazgo]:
    """Aumento de los días de pago del último mes frente al histórico del cliente (FIN-POL-004 §5)."""
    res = _q(
        con,
        corte,
        """
        WITH ult AS (
            SELECT cliente_id, mes_factura, dias_pago_prom
            FROM v_dias_pago_mensual
            QUALIFY row_number() OVER (PARTITION BY cliente_id ORDER BY mes_factura DESC) = 1
        ),
        hist AS (
            SELECT cliente_id, avg(dias_pago_prom) AS dias_pago_hist
            FROM v_dias_pago_mensual
            GROUP BY cliente_id
        )
        SELECT u.cliente_id, u.dias_pago_prom AS dias_pago_reciente, round(h.dias_pago_hist, 1) AS dias_pago_historico,
               round(100 * (u.dias_pago_prom - h.dias_pago_hist) / nullif(h.dias_pago_hist, 0), 1) AS aumento_pct,
               coalesce(round(c.saldo_vencido), 0) AS saldo_vencido, coalesce(round(c.saldo_abierto), 0) AS saldo_abierto
        FROM ult u
        JOIN hist h USING (cliente_id)
        JOIN v_cartera_cliente c USING (cliente_id)
        WHERE (u.dias_pago_prom - h.dias_pago_hist) / nullif(h.dias_pago_hist, 0) > ? / 100.0
        ORDER BY saldo_abierto DESC
        """,
        "v_dias_pago_mensual",
        "Clientes cuyos días de pago del último mes superan su histórico por encima del umbral",
        [u.dias_pago_aumento_pct],
    )
    hallazgos: list[Hallazgo] = []
    for r in _filas(res):
        riesgo = int(r["saldo_vencido"] or 0)
        hallazgos.append(
            Hallazgo(
                hallazgo_id=_hid("dias_pago", r["cliente_id"], corte),
                kpi=Kpi.DIAS_PAGO,
                regla="FIN-POL-004/dias_pago_aumento",
                severidad=Severidad.MEDIA,
                entidades=[EntidadRef(tipo=TipoEntidad.CLIENTE, id=str(r["cliente_id"]))],
                valor_observado=float(r["dias_pago_reciente"]),
                umbral=round(float(r["dias_pago_historico"]) * (1 + u.dias_pago_aumento_pct / 100.0), 1),
                corte=corte,
                dinero_en_riesgo_cop=riesgo,
                consulta_ids=[res.consulta.consulta_id],
                huella_causa=f"saldo_vencido|{r['cliente_id']}",
            )
        )
    return hallazgos


def _detectar_cobertura(con: Any, corte: date, u: Umbrales) -> list[Hallazgo]:
    """Quiebre inminente: cobertura crítica o clase A bajo el mínimo, con pedidos pendientes (OPE-POL-007 §2)."""
    res = _q(
        con,
        corte,
        """
        SELECT c.sku, c.bodega_id, c.clase_abc, c.cobertura_dias, c.demanda_prom_30d, c.unidades_pendientes, p.precio_lista
        FROM v_cobertura_inventario c
        JOIN (
            SELECT sku, precio_lista FROM lista_precios
            WHERE fecha_vigencia <= fecha_corte()
            QUALIFY row_number() OVER (PARTITION BY sku ORDER BY fecha_vigencia DESC) = 1
        ) p USING (sku)
        WHERE c.unidades_pendientes > 0
          AND (c.cobertura_dias < ? OR (c.clase_abc = 'A' AND c.cobertura_dias < ?))
        ORDER BY c.cobertura_dias ASC
        """,
        "v_cobertura_inventario",
        "SKU con cobertura crítica o de clase A bajo el mínimo y pedidos pendientes de despacho",
        [u.cobertura_dias_critica, u.cobertura_dias_clase_a],
    )
    hallazgos: list[Hallazgo] = []
    for r in _filas(res):
        cobertura = float(r["cobertura_dias"] or 0.0)
        demanda = float(r["demanda_prom_30d"] or 0.0)
        pendientes = int(r["unidades_pendientes"] or 0)
        precio = float(r["precio_lista"] or 0.0)
        critico = cobertura < u.cobertura_dias_critica
        dias_quiebre = max(1.0, u.cobertura_dias_clase_a - cobertura)
        riesgo = int(round(max(demanda * precio * dias_quiebre, pendientes * precio)))
        hallazgos.append(
            Hallazgo(
                hallazgo_id=_hid("cobertura", r["sku"], r["bodega_id"], corte),
                kpi=Kpi.COBERTURA,
                regla="OPE-POL-007/cobertura_critica" if critico else "OPE-POL-007/cobertura_clase_a",
                severidad=Severidad.CRITICA if critico else Severidad.ALTA,
                entidades=[
                    EntidadRef(tipo=TipoEntidad.SKU, id=str(r["sku"])),
                    EntidadRef(tipo=TipoEntidad.BODEGA, id=str(r["bodega_id"])),
                ],
                valor_observado=cobertura,
                umbral=u.cobertura_dias_critica if critico else u.cobertura_dias_clase_a,
                corte=corte,
                dinero_en_riesgo_cop=riesgo,
                consulta_ids=[res.consulta.consulta_id],
                huella_causa=f"cobertura_dias|{r['sku']}",
            )
        )
    return hallazgos


def _detectar_descuentos(con: Any, corte: date, u: Umbrales) -> list[Hallazgo]:
    """Descuentos sobre el tope del segmento sin aprobación, por vendedor (COM-POL-002 §2-5)."""
    res = _q(
        con,
        corte,
        """
        SELECT vendedor_id, count(*) AS lineas, count(DISTINCT date_trunc('week', fecha)) AS semanas,
               round(sum(descuento_en_exceso)) AS total_exceso, min(fecha) AS desde
        FROM v_descuentos_fuera_politica
        GROUP BY vendedor_id
        HAVING count(DISTINCT date_trunc('week', fecha)) >= ? OR count(*) >= ?
        ORDER BY total_exceso DESC
        """,
        "v_descuentos_fuera_politica",
        "Vendedores con descuentos sobre el tope sin aprobación especial (dos semanas o volumen alto)",
        [u.descuento_semanas, u.descuento_lineas_min],
    )
    hallazgos: list[Hallazgo] = []
    for r in _filas(res):
        exceso = int(r["total_exceso"] or 0)
        hallazgos.append(
            Hallazgo(
                hallazgo_id=_hid("descuento", r["vendedor_id"], corte),
                kpi=Kpi.DESCUENTO_EXCESO,
                regla="COM-POL-002/descuento_exceso",
                severidad=Severidad.ALTA,
                entidades=[EntidadRef(tipo=TipoEntidad.VENDEDOR, id=str(r["vendedor_id"]))],
                valor_observado=float(r["lineas"]),
                umbral=float(u.descuento_lineas_min),
                corte=corte,
                dinero_en_riesgo_cop=exceso,
                consulta_ids=[res.consulta.consulta_id],
                huella_causa=f"descuento_en_exceso|{r['vendedor_id']}",
            )
        )
    return hallazgos


def _detectar_inactividad(con: Any, corte: date, u: Umbrales) -> list[Hallazgo]:
    """Cliente habitual que supera N veces su intervalo de compra (metricas.yaml)."""
    res = _q(
        con,
        corte,
        """
        WITH inactivos AS (
            SELECT cliente_id, pedidos, ultima_compra, intervalo_prom_dias, dias_sin_comprar, veces_intervalo_habitual
            FROM v_actividad_cliente
            WHERE veces_intervalo_habitual > ? AND pedidos >= ?
        ),
        ventas AS (
            SELECT i.cliente_id, coalesce(round(sum(v.valor_neto) / 3.0), 0) AS ventas_prom_mensual
            FROM inactivos i
            JOIN v_ventas v ON v.cliente_id = i.cliente_id
                           AND v.fecha >= i.ultima_compra - INTERVAL 90 DAY AND v.fecha <= i.ultima_compra
            GROUP BY i.cliente_id
        )
        SELECT i.cliente_id, i.pedidos, i.ultima_compra, i.intervalo_prom_dias, i.dias_sin_comprar,
               i.veces_intervalo_habitual, coalesce(v.ventas_prom_mensual, 0) AS ventas_prom_mensual
        FROM inactivos i
        LEFT JOIN ventas v USING (cliente_id)
        ORDER BY i.veces_intervalo_habitual DESC
        """,
        "v_actividad_cliente",
        "Clientes con 10 o más pedidos cuyo tiempo sin comprar supera el umbral de veces su intervalo habitual",
        [u.intervalo_veces, u.intervalo_pedidos_min],
    )
    hallazgos: list[Hallazgo] = []
    for r in _filas(res):
        riesgo = int(r["ventas_prom_mensual"] or 0)
        hallazgos.append(
            Hallazgo(
                hallazgo_id=_hid("inactividad", r["cliente_id"], corte),
                kpi=Kpi.INTERVALO_COMPRA,
                regla="metricas/intervalo_compra",
                severidad=_sev_por_monto(riesgo, 20_000_000),
                entidades=[EntidadRef(tipo=TipoEntidad.CLIENTE, id=str(r["cliente_id"]))],
                valor_observado=float(r["veces_intervalo_habitual"]),
                umbral=u.intervalo_veces,
                corte=corte,
                dinero_en_riesgo_cop=riesgo,
                consulta_ids=[res.consulta.consulta_id],
                huella_causa=f"veces_intervalo_habitual|{r['cliente_id']}",
            )
        )
    return hallazgos


def _detectar_venta_bajo_costo(con: Any, corte: date, u: Umbrales) -> list[Hallazgo]:
    """Líneas vendidas con valor neto menor al costo, agrupadas por SKU (COM-POL-002 §4)."""
    res = _q(
        con,
        corte,
        """
        SELECT sku, count(*) AS lineas, round(sum(costo_total - valor_neto)) AS perdida_directa
        FROM v_ventas
        WHERE valor_neto < costo_total
        GROUP BY sku
        HAVING sum(costo_total - valor_neto) > ?
        ORDER BY perdida_directa DESC
        """,
        "v_ventas",
        "SKU vendidos con valor neto menor al costo y su pérdida directa acumulada",
        [u.venta_bajo_costo_min_cop],
    )
    hallazgos: list[Hallazgo] = []
    for r in _filas(res):
        perdida = int(r["perdida_directa"] or 0)
        hallazgos.append(
            Hallazgo(
                hallazgo_id=_hid("bajo_costo", r["sku"], corte),
                kpi=Kpi.VENTA_BAJO_COSTO,
                regla="COM-POL-002/venta_bajo_costo",
                severidad=Severidad.ALTA,
                entidades=[EntidadRef(tipo=TipoEntidad.SKU, id=str(r["sku"]))],
                valor_observado=float(perdida),
                umbral=float(u.venta_bajo_costo_min_cop),
                corte=corte,
                dinero_en_riesgo_cop=perdida,
                consulta_ids=[res.consulta.consulta_id],
                huella_causa=f"venta_bajo_costo|{r['sku']}",
            )
        )
    return hallazgos


# -----------------------------------------------------------------------------
# Detección, correlación por causa raíz y alertas
# -----------------------------------------------------------------------------
def _asociar_margen_a_costo(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    """La caída de margen de una línea se une a la causa de costo del proveedor que afecta SKU de esa línea."""
    causa_por_linea: dict[str, tuple[int, str]] = {}
    for h in hallazgos:
        if not h.huella_causa.startswith("costo|"):
            continue
        linea = next((e.id for e in h.entidades if e.tipo == TipoEntidad.LINEA), None)
        if linea and h.dinero_en_riesgo_cop >= causa_por_linea.get(linea, (-1, ""))[0]:
            causa_por_linea[linea] = (h.dinero_en_riesgo_cop, h.huella_causa)

    resultado: list[Hallazgo] = []
    for h in hallazgos:
        if h.huella_causa.startswith("margen|"):
            linea = h.huella_causa.split("|", 1)[1]
            if linea in causa_por_linea:
                h = h.model_copy(update={"huella_causa": causa_por_linea[linea][1]})
        resultado.append(h)
    return resultado


def detectar_hallazgos(corte: date, con: Any = None, umbrales: Umbrales | None = None) -> list[Hallazgo]:
    """Ejecuta las reglas de los 6 KPIs y la de venta bajo costo al corte indicado."""
    u = umbrales or cargar_umbrales()
    cerrar_con = con is None
    if con is None:
        con = get_duckdb_connection(corte)
    try:
        hallazgos: list[Hallazgo] = []
        for regla in (
            _detectar_costo_proveedor,
            _detectar_margen_linea,
            _detectar_cartera,
            _detectar_dias_pago,
            _detectar_cobertura,
            _detectar_descuentos,
            _detectar_inactividad,
            _detectar_venta_bajo_costo,
        ):
            hallazgos.extend(regla(con, corte, u))
        return _asociar_margen_a_costo(hallazgos)
    finally:
        if cerrar_con:
            con.close()


def _monto_alerta(huella: str, items: list[Hallazgo]) -> int:
    """Dinero en riesgo de la causa, sin doble conteo."""
    if huella.startswith("saldo_vencido|"):
        return max(h.dinero_en_riesgo_cop for h in items)
    if huella.startswith("costo|"):
        sobrecosto = sum(h.dinero_en_riesgo_cop for h in items if h.regla.startswith("OPE-POL-007/costo"))
        margen = max((h.dinero_en_riesgo_cop for h in items if h.kpi == Kpi.MARGEN and not h.regla.startswith("OPE-POL-007/costo")), default=0)
        return max(sobrecosto, margen)
    return sum(h.dinero_en_riesgo_cop for h in items)


def generar_alertas(corte: date, con: Any = None, umbrales: Umbrales | None = None) -> list[Alerta]:
    """Agrupa los hallazgos por causa (`huella_causa`) y devuelve una alerta por causa, por dinero en riesgo."""
    inicio = time.perf_counter()
    hallazgos = detectar_hallazgos(corte, con=con, umbrales=umbrales)

    grupos: dict[str, list[Hallazgo]] = defaultdict(list)
    for h in hallazgos:
        grupos[h.huella_causa].append(h)

    alertas: list[Alerta] = []
    ahora = datetime.now(timezone.utc)
    for huella, items in grupos.items():
        severidad = max(items, key=lambda x: _SEVERIDAD_RANK.get(x.severidad, 0)).severidad
        alerta_id = f"ALR-{corte.strftime('%Y%m%d')}-{hashlib.sha1(huella.encode('utf-8')).hexdigest()[:6]}"
        alerta = Alerta(
            schema_version=SCHEMA_VERSION,
            alerta_id=alerta_id,
            estado=EstadoAlerta.NUEVA,
            huella_causa=huella,
            hallazgos=items,
            severidad=severidad,
            dinero_en_riesgo_cop=_monto_alerta(huella, items),
            corte_creacion=corte,
            creada_en=ahora,
            version=1,
        )
        alertas.append(alerta)
        emitir_alertas_generadas(kpi=items[0].kpi.value, severidad=severidad.value, count=1)

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
