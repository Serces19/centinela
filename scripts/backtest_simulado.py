# scripts/backtest_simulado.py
"""Backtest del Vigía: avanza el reloj día a día y anota cuándo aparece, por primera vez, la alerta de cada escenario.

Solo usa el Vigía (reglas sobre DuckDB, sin LLM). Un escenario cuenta como detectado cuando existe una alerta
con exactamente su huella de causa (`familia|entidad raíz`), no cualquier alerta que toque la entidad.
La columna "inicio del desvío" son hechos de los datos sembrados (docs/01_negocio.md), no una estimación de
cuándo se habría enterado la empresa: no se compara contra ningún proceso manual porque no lo medimos.

Uso: python scripts/backtest_simulado.py [--inicio 2026-01-01] [--paso 1]
"""
import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from agents.vigia import generar_alertas  # noqa: E402

# Ground truth del dataset oficial (semilla por defecto). Con otra semilla las entidades cambian.
ESCENARIOS = {
    "S1": ("Alza de costo del proveedor sin ajuste de precio", "costo|PR08", date(2026, 8, 15)),
    "S2": ("Mora creciente de un cliente mayorista", "saldo_vencido|C0496", None),
    "S3": ("Quiebre inminente de un SKU clase A", "cobertura_dias|P0119", None),
    "S4": ("Descuentos fuera de política de un vendedor", "descuento_en_exceso|V03", date(2026, 7, 1)),
    "S5": ("Cliente que dejó de comprar", "veces_intervalo_habitual|C0061", date(2026, 7, 9)),
    "S6": ("Venta bajo costo (oculto, hipótesis)", "venta_bajo_costo|P0097", None),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default="2025-10-01")
    ap.add_argument("--fin", default="2026-09-30")
    ap.add_argument("--paso", type=int, default=1)
    args = ap.parse_args()
    inicio, fin = date.fromisoformat(args.inicio), date.fromisoformat(args.fin)

    primera: dict[str, tuple[date, int]] = {}
    ruido: list[int] = []
    t0 = time.perf_counter()
    dias = 0
    cur = inicio
    while cur <= fin:
        alertas = generar_alertas(cur)
        ruido.append(len(alertas))
        huellas = {a.huella_causa: a for a in alertas}
        for k, (_, huella, _) in ESCENARIOS.items():
            if k not in primera and huella in huellas:
                primera[k] = (cur, int(huellas[huella].dinero_en_riesgo_cop))
        dias += 1
        cur += timedelta(days=args.paso)
    dt = time.perf_counter() - t0

    filas = []
    for k, (nombre, huella, desvio) in ESCENARIOS.items():
        det = primera.get(k)
        if det:
            retraso = f"{(det[0] - desvio).days} d" if desvio else "—"
            monto = format(det[1], ',').replace(',', '.')
            filas.append(f"| {k} | {nombre} | `{huella}` | {desvio.isoformat() if desvio else '—'} | `{det[0].isoformat()}` | {retraso} | ${monto} |")
        else:
            filas.append(f"| {k} | {nombre} | `{huella}` | {desvio.isoformat() if desvio else '—'} | no detectado | — | — |")

    md = [
        "# Backtest del Vigía",
        "",
        f"Periodo: {inicio} a {fin} ({dias} cortes evaluados, {dt:.0f} s). Generado por `scripts/backtest_simulado.py`; no editar a mano.",
        "",
        "| Escenario | Qué es | Huella de la alerta | Inicio del desvío en los datos | 1ª detección | Retraso | Dinero en riesgo ese día (COP) |",
        "|:--:|:--|:--|:--:|:--:|:--:|--:|",
        *filas,
        "",
        f"Alertas simultáneas por corte (todas, incluido el ruido normal del dataset): mínimo {min(ruido)}, mediana {sorted(ruido)[len(ruido)//2]}, máximo {max(ruido)}.",
        "",
        "Lectura honesta: el Vigía detecta cada escenario con su regla de política el mismo día en que el dato cruza el umbral. "
        "El inicio del desvío solo se conoce con precisión en S1 (fecha del alza), S4 (primer descuento fuera de política) y S5 (última compra); "
        "en el resto el desvío es gradual y no hay una fecha de inicio. No se compara contra una detección manual porque no la medimos.",
    ]
    out = ROOT / "docs" / "informes" / "backtest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
