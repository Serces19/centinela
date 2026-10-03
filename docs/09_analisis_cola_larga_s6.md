# Hallazgos de Exploración de Cola Larga y Diagnóstico del Escenario Oculto (S6)

**Fecha de corte:** 2026-09-30  
**Tiempo de análisis multidimensional:** 0.19 s  
**Motor:** DuckDB In-Memory sobre 15 tablas relacionales (≈270k registros)  

## 1. Hipótesis Principal S6: Venta Sistemática Bajo Costo en SKUs Críticos

Al cruzar `v_ventas` contra la política comercial `COM-POL-002 (§4: Prohibición de venta bajo costo unitario)`, se aislaron patrones de venta bajo costo que generan pérdidas directas de margen:

| SKU | Nombre Producto | Línea | Vendedor | Líneas Afectadas | Pérdida Total (COP) | % Pérdida Media |
|:---:|:---|:---|:---:|:---:|---:|:---:|
| `P0097` | Leche en polvo x1 (ALI-32) | Alimentos | Laura Cárdenas (`V06`) | 10 | **$784,944 COP** | -15.7% |
| `P0097` | Leche en polvo x1 (ALI-32) | Alimentos | Felipe Ospina (`V07`) | 14 | **$403,137 COP** | -15.7% |
| `P0097` | Leche en polvo x1 (ALI-32) | Alimentos | Diego Morales (`V15`) | 11 | **$186,993 COP** | -15.7% |
| `P0088` | Lentejas 3 L (ALI-23) | Alimentos | Juan Pablo Ríos (`V03`) | 6 | **$142,644 COP** | -2.9% |
| `P0097` | Leche en polvo x1 (ALI-32) | Alimentos | Sebastián Castro (`V11`) | 7 | **$101,673 COP** | -15.7% |

## 2. Puntos Ciegos de Margen por Línea de Negocio y Canal

Combinaciones con margen significativamente inferior al promedio histórico mediante Z-Score robusto (MAD):

| Línea de Producto | Canal de Venta | Pedidos | Venta Neta (COP) | Margen Bruto % | Z-Score Robust |
|:---|:---|---:|---:|:---:|:---:|

## 3. Descuentos Fuera de Política por Segmento y Canal

| Canal | Segmento | Ventas Evaluadas | Descuento Promedio % | Descuento Máximo % | Exceso Total (COP) |
|:---|:---|---:|:---:|:---:|---:|
| Asesor en campo | Mayoristas | 82 | 20.98% | 24.90% | **$3,386,062 COP** |
| Portal B2B | Mayoristas | 50 | 21.67% | 25.00% | **$1,723,165 COP** |
| Televenta | Mayoristas | 34 | 22.19% | 25.00% | **$1,106,403 COP** |
| Asesor en campo | Minoristas | 85 | 21.28% | 24.90% | **$1,065,541 COP** |
| Televenta | Minoristas | 35 | 21.55% | 24.80% | **$514,626 COP** |
| Portal B2B | Minoristas | 30 | 21.44% | 24.80% | **$301,046 COP** |

## Recomendación Estratégica para Distribuidora Andina

1. **Bloqueo preventivo en ERP:** Configurar validación a nivel de línea de pedido para impedir la facturación de `P0097` y `P0006` cuando el precio pactado sea menor al costo estándar vigente.
2. **Capacitación y auditoría a la fuerza de ventas:** Notificar inmediatamente a los vendedores reincidentes mediante Centinela para alinear los acuerdos comerciales a las bandas autorizadas de `COM-POL-002`.