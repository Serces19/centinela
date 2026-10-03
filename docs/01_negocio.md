# 01 · Negocio: Distribuidora Andina y los KPIs de Centinela

Fuente: `Kit_Equipos/datos/metricas.yaml`, `03_capa_semantica.sql`, políticas PDF, exploración propia de los CSV (corte 2026-09-30).

## Empresa
Distribuidora de consumo masivo (COP), 2 bodegas (BOD-MDE, BOD-BOG), 500 clientes, 200 SKU en 7 líneas, 25 vendedores, 40 proveedores. ≈ $23.500 M ventas netas en 12 meses.

## Las métricas: son 6 KPIs (+ 1 vista base = las "7 vistas")
`metricas.yaml` define **6 KPIs**; el kit trae **7 vistas** porque `v_ventas` es la vista base de la que sale el margen.

| # | KPI | Vista | Fórmula | Umbral de alerta (política) | Dueño del problema |
|---|---|---|---|---|---|
| 1 | `margen_pct` | `v_margen_semanal_linea` | 1 − Σcosto/Σventa neta | caída > 3 pp vs prom. 8 semanas previas, o margen < mínimo de línea | Comercial / Compras |
| 2 | `saldo_vencido` | `v_cartera_cliente` | facturas abiertas con vencimiento < corte | max_dias_vencido > 15, o saldo_abierto > cupo | Cartera / Finanzas |
| 3 | `dias_pago_prom` | `v_dias_pago_mensual` | prom. (fecha_pago − fecha_factura) por mes de factura | aumento > 50% vs histórico del cliente | Cartera |
| 4 | `cobertura_dias` | `v_cobertura_inventario` | existencia / demanda diaria prom. 30d | < 10 d clase A (7 B, 5 C); **crítico < 5 d con pedidos pendientes** | Compras |
| 5 | `descuento_en_exceso` | `v_descuentos_fuera_politica` | descuento sobre tope del segmento sin aprobación | cualquier línea; agrupar por vendedor y semana | Control Comercial |
| 6 | `veces_intervalo_habitual` | `v_actividad_cliente` | días sin comprar / intervalo habitual | > 3× en clientes con ≥ 10 pedidos | Vendedor / Comercial |

## Reglas de política que el Analista debe citar (RAG)
- **Crédito (FIN-POL-004):** plazos 60/45/30/45 d (Grandes/Mayoristas/Minoristas/Institucional). Escalamiento: 1-15 recordatorio · 16-30 llamada + alerta al vendedor · 31-60 solo contado · >60 bloqueo de despachos. Alerta temprana: días de pago +50% vs histórico, o >10% de la cartera vencida total.
- **Descuentos (COM-POL-002):** topes 18/15/10/12 %, hasta 21/18/13/15 % con aprobación (`aprobacion_especial='S'`). Prohibido vender bajo costo sin aprobación de Gerencia General. **2 semanas consecutivas fuera de política → pierde facultad de cotizar.**
- **Inventario/precios (OPE-POL-007):** cobertura mín. A=10, B=7, C=5 d. OC retrasada → contactar proveedor el mismo día, evaluar alterno/entrega parcial. **Costo +5% → Comercial revisa precio en ≤ 10 días hábiles.** Márgenes mínimos: Hogar 25, Aseo 22, Alimentos 15, Bebidas 18, Cuidado personal 25, Mascotas 22, Papelería 28.

## Escenarios sembrados: hallazgos en el dataset oficial (verificados con DuckDB)
| # | Escenario | Entidad encontrada | Evidencia |
|---|---|---|---|
| S1 | Margen que se erosiona | Línea **Hogar**, proveedor **PR08**, SKU P0001/P0006/P0011/P0021 | costo +28–34 %; margen Hogar 28.1 % (may) → 22.3 % (sep), mínimo 25 % |
| S2 | Mora creciente | Cliente **C0496** | días de pago 29 → 66 |
| S3 | Quiebre inminente | **P0119 Gaseosa 3 L**, **BOD-MDE**, clase A | cobertura 3.5 d; OC retrasada (1 en el dataset) |
| S4 | Descuentos fuera de política | Vendedor **V03** (Caribe) | 316 líneas, ≈ $8,1 M de exceso |
| S5 | Cliente que se va | Cliente **C0061** | 12.5× su intervalo (último pedido 2026-07-09, 43 pedidos) |
| S6 | **Oculto** (se revela al cierre) | ¿? | Candidatos a investigar: 42 líneas con precio < costo; Alimentos en 14.2 % (< mín. 15 %); otros cortes dimensión×tiempo |

> Estas entidades **no se hardcodean**: el generador (`SEMILLA=n`) las cambia y el jurado puede probar con otra semilla. Solo sirven como ground truth del set de evaluación.

## Datos a vigilar (trampas de calidad)
- 781 pedidos cancelados (excluidos de `v_ventas`); facturas ≠ pedidos (19.085 vs 20.013).
- Mapeo ciudad→bodega está hardcodeado en `v_cobertura_inventario`.
- `fecha_corte()` = max(inventario_diario.fecha): con reloj simulado hay que parametrizar **todas** las vistas (incluida cartera y pagos con `fecha_pago <= corte`).
- Costos/precios con vigencias (`costos_proveedor`, `lista_precios`): alza de costo se detecta ahí, no en `v_ventas`.
