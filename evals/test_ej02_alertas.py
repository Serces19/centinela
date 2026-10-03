"""Evaluación EJ-02: Verificación de alertas y detección del Agente Vigía.

Comprueba determinismo, deduplicación, reglas de política y fechas clave:
- Con corte 2026-09-30: se detectan los 5 escenarios principales (S1 PR08, S2 C0496, S3 P0119, S4 V03, S5 C0061).
- Con corte 2026-08-15: aparece S1 (PR08).
- Con corte 2026-06-30: NO aparecen S1, S3, S4 ni S5.
- Corte inicial limpio (2026-06-18): no hay ninguna alerta de S1 a S5.
- Estadística de apoyo: caída de margen de Hogar detectada por z-score robusto (MAD).
- Deduplicación: S1 genera 1 sola alerta para los 4 SKUs de PR08.
- Prioridad: las alertas se ordenan de mayor a menor dinero en riesgo.
"""

from datetime import date
import pytest

from agents.vigia import (
    analizar_caida_margen_linea,
    calcular_zscore_robusto,
    detectar_hallazgos,
    generar_alertas,
)
from contracts.base import (
    Severidad,
    TipoEntidad,
)
from contracts.configuracion import CORTE_INICIAL_LIMPIO



def test_deteccion_escenarios_corte_2026_09_30():
    """Con corte 2026-09-30 se detectan los 5 escenarios principales con sus entidades exactas."""
    corte = date(2026, 9, 30)
    alertas = generar_alertas(corte)

    # 1. Priorización: ordenadas por dinero en riesgo descendente
    assert len(alertas) > 0
    for i in range(len(alertas) - 1):
        assert alertas[i].dinero_en_riesgo_cop >= alertas[i + 1].dinero_en_riesgo_cop

    # 2. S1: Margen / Costo PR08
    alr_s1 = next((a for a in alertas if a.huella_causa == "costo|PR08"), None)
    assert alr_s1 is not None, "Alerta S1 (costo|PR08) no fue detectada"
    assert alr_s1.severidad in (Severidad.ALTA, Severidad.CRITICA)
    assert len(alr_s1.hallazgos) == 4
    skus_s1 = {e.id for h in alr_s1.hallazgos for e in h.entidades if e.tipo == TipoEntidad.SKU}
    assert skus_s1 == {"P0001", "P0006", "P0011", "P0021"}
    assert alr_s1.dinero_en_riesgo_cop > 20_000_000

    # 3. S2: Mora C0496
    alr_s2 = next((a for a in alertas if a.huella_causa == "saldo_vencido|C0496"), None)
    assert alr_s2 is not None, "Alerta S2 (saldo_vencido|C0496) no fue detectada"
    assert alr_s2.severidad in (Severidad.ALTA, Severidad.CRITICA)
    assert alr_s2.dinero_en_riesgo_cop == 48647744

    # 4. S3: Quiebre inminente P0119 en BOD-MDE
    alr_s3 = next((a for a in alertas if a.huella_causa == "cobertura_dias|P0119"), None)
    assert alr_s3 is not None, "Alerta S3 (cobertura_dias|P0119) no fue detectada"
    assert alr_s3.severidad == Severidad.CRITICA
    bodegas_s3 = {e.id for h in alr_s3.hallazgos for e in h.entidades if e.tipo == TipoEntidad.BODEGA}
    assert "BOD-MDE" in bodegas_s3
    assert alr_s3.dinero_en_riesgo_cop > 0

    # 5. S4: Descuentos en exceso V03
    alr_s4 = next((a for a in alertas if a.huella_causa == "descuento_en_exceso|V03"), None)
    assert alr_s4 is not None, "Alerta S4 (descuento_en_exceso|V03) no fue detectada"
    assert alr_s4.severidad == Severidad.ALTA
    assert abs(alr_s4.dinero_en_riesgo_cop - 8096844) <= 1

    # 6. S5: Cliente inactivo C0061
    alr_s5 = next((a for a in alertas if a.huella_causa == "veces_intervalo_habitual|C0061"), None)
    assert alr_s5 is not None, "Alerta S5 (veces_intervalo_habitual|C0061) no fue detectada"
    assert alr_s5.severidad in (Severidad.ALTA, Severidad.CRITICA)
    assert alr_s5.dinero_en_riesgo_cop == 29469987

    # 7. S6: Venta bajo costo
    alr_s6 = next((a for a in alertas if a.huella_causa.startswith("venta_bajo_costo")), None)
    assert alr_s6 is not None, "Alerta S6 (venta_bajo_costo) no fue detectada"


def test_deteccion_escenarios_corte_2026_08_15():
    """Con corte 2026-08-15 aparece S1 (PR08) con impacto mensual ≈ $23.55M COP y NO aparece S3."""
    corte = date(2026, 8, 15)
    alertas = generar_alertas(corte)

    # S1 presente con sus 4 SKUs
    alr_s1 = next((a for a in alertas if a.huella_causa == "costo|PR08"), None)
    assert alr_s1 is not None, "Alerta S1 debe aparecer el 2026-08-15"
    assert abs(alr_s1.dinero_en_riesgo_cop - 23558346) / 23558346 < 0.01
    assert len(alr_s1.hallazgos) == 4

    # S3 NO debe aparecer el 2026-08-15 (cobertura era normal de 32 días)
    alr_s3 = next((a for a in alertas if a.huella_causa == "cobertura_dias|P0119"), None)
    assert alr_s3 is None, "Alerta S3 no debe existir a 2026-08-15"


def test_deteccion_escenarios_corte_2026_06_30():
    """Con corte 2026-06-30 NO aparecen S1, S3, S4 ni S5."""
    corte = date(2026, 6, 30)
    alertas = generar_alertas(corte)
    huellas = {a.huella_causa for a in alertas}

    # S1 no ha subido costo (ocurre el 2026-08-15)
    assert "costo|PR08" not in huellas

    # S3 inventario normal (cobertura 52.9 días)
    assert "cobertura_dias|P0119" not in huellas

    # S4 V03 no ha dado descuentos fuera de política (comienza el 2026-07-01)
    assert "descuento_en_exceso|V03" not in huellas

    # S5 C0061 compra activamente hasta el 2026-07-09
    assert "veces_intervalo_habitual|C0061" not in huellas

    # S2 C0496 sí comenzó su mora (alcanzó 17 días de mora el 2026-06-20)
    assert "saldo_vencido|C0496" in huellas


def test_corte_inicial_limpio():
    """A la fecha de corte inicial limpio (2026-06-18) ninguna alerta de S1 a S5 está activa."""
    alertas = generar_alertas(CORTE_INICIAL_LIMPIO)
    huellas = {a.huella_causa for a in alertas}

    assert "costo|PR08" not in huellas
    assert "saldo_vencido|C0496" not in huellas
    assert "cobertura_dias|P0119" not in huellas
    assert "descuento_en_exceso|V03" not in huellas
    assert "veces_intervalo_habitual|C0061" not in huellas


def test_estadistica_apoyo_zscore_hogar():
    """Tarea 1.8: z-score robusto (MAD) detecta la caída de margen de Hogar."""
    reciente, mediana, z_score = analizar_caida_margen_linea("Hogar", date(2026, 9, 30))

    # El margen cayó a ~22.38% frente a una mediana histórica de ~27.5%
    assert reciente < 25.0
    assert mediana > 26.5
    assert z_score < -2.5  # Caída estadísticamente anómala (> 2.5 desviaciones robustas)


def test_deduplicacion_y_prioridad_s1():
    """Tarea 1.10: Deduplicación de 4 SKUs bajo la misma huella_causa y ordenamiento descendente."""
    corte = date(2026, 9, 30)
    alertas = generar_alertas(corte)

    # Debe haber una y solo una alerta para el proveedor PR08
    alertas_pr08 = [a for a in alertas if a.huella_causa == "costo|PR08"]
    assert len(alertas_pr08) == 1
    alr = alertas_pr08[0]
    assert len(alr.hallazgos) == 4

    # Cada alerta tiene un ID determinista válido
    assert alr.alerta_id.startswith(f"ALR-{corte.strftime('%Y%m%d')}-")
    assert len(alr.alerta_id) == 19  # ALR-yyyymmdd-xxxxxx
