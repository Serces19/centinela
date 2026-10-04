# Backtest del Vigía

Periodo: 2025-10-01 a 2026-09-30 (365 cortes evaluados, 114 s). Generado por `scripts/backtest_simulado.py`; no editar a mano.

| Escenario | Qué es | Huella de la alerta | Inicio del desvío en los datos | 1ª detección | Retraso | Dinero en riesgo ese día (COP) |
|:--:|:--|:--|:--:|:--:|:--:|--:|
| S1 | Alza de costo del proveedor sin ajuste de precio | `costo|PR08` | 2026-08-15 | `2026-08-15` | 0 d | $23.522.184 |
| S2 | Mora creciente de un cliente mayorista | `saldo_vencido|C0496` | — | `2026-06-19` | — | $22.136.511 |
| S3 | Quiebre inminente de un SKU clase A | `cobertura_dias|P0119` | — | `2026-09-29` | — | $6.212.680 |
| S4 | Descuentos fuera de política de un vendedor | `descuento_en_exceso|V03` | 2026-07-01 | `2026-07-03` | 2 d | $330.433 |
| S5 | Cliente que dejó de comprar | `veces_intervalo_habitual|C0061` | 2026-07-09 | `2026-07-30` | 21 d | $29.469.987 |
| S6 | Venta bajo costo (oculto, hipótesis) | `venta_bajo_costo|P0097` | — | `2026-09-04` | — | $535.383 |

Alertas simultáneas por corte (todas, incluido el ruido normal del dataset): mínimo 0, mediana 112, máximo 149.

Lectura honesta: el Vigía detecta cada escenario con su regla de política el mismo día en que el dato cruza el umbral. El inicio del desvío solo se conoce con precisión en S1 (fecha del alza), S4 (primer descuento fuera de política) y S5 (última compra); en el resto el desvío es gradual y no hay una fecha de inicio. No se compara contra una detección manual porque no la medimos.
