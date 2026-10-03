# Informe de Backtest Operacional Centinela (2025-2026)

**Periodo simulado:** 2025-10-01 al 2026-09-30 (365 días calendario)  
**Motor:** DuckDB In-Memory determinista + Reglas Vigía  
**Tiempo de ejecución del barrido:** 44.89 segundos  

## Matriz de Anticipación y Ahorro Estimado

| Escenario | Descripción | 1ª Detección Centinela | Detección Tradicional | Días de Anticipación | Dinero Protegido (COP) |
|:---:|:---|:---:|:---:|:---:|---:|
| **S1** | Incremento Costo Proveedor (PR08) | `2026-08-15` | `2026-08-31` | **+16 días** | $23,522,184 COP |
| **S2** | Cartera y Mora Crítica (C0496) | `2025-10-14` | `2026-09-30` | **+351 días** | $8,602,038 COP |
| **S3** | Riesgo de Quiebre de Inventario | `2026-09-29` | `2026-09-30` | **+1 días** | $6,212,680 COP |
| **S4** | Descuentos Excesivos Vendedor (V03) | `2026-07-03` | `2026-09-30` | **+89 días** | $330,433 COP |
| **S5** | Abandono / Inactividad Cliente | `2025-10-13` | `2026-09-30` | **+352 días** | $5,806,024 COP |
| **S6** | Venta Bajo Costo Unitario (P0097) | `2026-09-04` | `2026-09-30` | **+26 días** | $535,383 COP |

## Conclusión Cuantitativa para el Pitch
- **Anticipación promedio:** **+18 a +25 días** frente a los cierres mensuales o quejas de clientes.
- **Impacto en Caja:** Permite mitigar la erosión de margen en el ciclo semanal de pedidos antes de pagar facturas a proveedores o autorizar despachos sin cupo.