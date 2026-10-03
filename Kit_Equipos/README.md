# Centinela · kit de datos para equipos

Hackatón Business AI School · On Business · Medellín

Datos de **Distribuidora Andina S.A.S.**, una distribuidora ficticia de consumo masivo con dos bodegas (Medellín y Bogotá),
500 clientes, 200 productos y 25 vendedores. Cubre 12 meses: del **2025-10-01 al 2026-09-30**. Valores en pesos colombianos (COP).
Todos los nombres y cifras son sintéticos.

## Contenido

| Archivo | Contenido | Filas |
|---|---|---|
| `vendedores.csv` | Fuerza de ventas | 25 |
| `clientes.csv` | Clientes de la distribuidora | 500 |
| `proveedores.csv` | Proveedores | 40 |
| `productos.csv` | Catálogo de productos | 200 |
| `bodegas.csv` | Centros de distribución | 2 |
| `lista_precios.csv` | Precio de lista vigente por SKU | 400 |
| `costos_proveedor.csv` | Costo de compra vigente por SKU | 2.404 |
| `ordenes_compra.csv` | Órdenes de compra a proveedores | 3.802 |
| `pedidos.csv` | Encabezado de pedidos de venta | 20.013 |
| `pedidos_detalle.csv` | Líneas de pedido | 60.103 |
| `facturas.csv` | Facturas electrónicas | 19.085 |
| `pagos.csv` | Pagos recibidos | 17.010 |
| `inventario_diario.csv` | Existencias diarias por SKU y bodega | 146.000 |
| `ref_topes_descuento.csv` | Topes de descuento por segmento (de la política) | 4 |
| `ref_margen_minimo_linea.csv` | Margen mínimo por línea (de la política) | 7 |

- `datos/sql/01_esquema.sql`: tablas en PostgreSQL (esquema `centinela`).
- `datos/sql/02_carga.sql`: carga de los CSV con `\copy`.
- `datos/sql/03_capa_semantica.sql`: vistas de métricas para los agentes (margen, cartera, cobertura, descuentos, actividad).
- `datos/metricas.yaml`: definición única de cada métrica y su umbral de alerta.
- `politicas/`: políticas de crédito, descuentos e inventario en PDF, para búsqueda (RAG).
- `diccionario_de_datos.xlsx`: tablas, campos, tipos y ejemplos.
- `evaluaciones/plantilla_casos_prueba.csv`: formato sugerido para su set de evaluaciones.
- `generador/generar_dataset.py`: genera datasets alternativos para sus propias pruebas.

## Puesta en marcha (5 minutos)

```bash
createdb centinela
cd datos
psql -d centinela -f sql/01_esquema.sql
psql -d centinela -f sql/02_carga.sql
psql -d centinela -f sql/03_capa_semantica.sql
psql -d centinela -c "SELECT * FROM centinela.v_cobertura_inventario ORDER BY cobertura_dias LIMIT 5;"
```

Para los agentes, creen un usuario de **solo lectura** con acceso únicamente a las vistas `v_*`.

## Reloj simulado

La fecha de corte por defecto es el último día del dataset (`centinela.fecha_corte()`). Para la demo, su sistema debe poder
"vivir" cualquier día: filtren todas las consultas con `fecha <= <día simulado>` y avancen el reloj día a día.

## Escenarios

El dataset tiene 5 problemas de negocio anunciados (margen que se erosiona, mora creciente, quiebre de stock inminente,
descuentos fuera de política, cliente que se va) y uno oculto que se revela al cierre. No sabemos qué entidades afectan: eso
lo debe descubrir Centinela.

## Generador

`python generador/generar_dataset.py` crea otro dataset con la misma estructura y escenarios en otras entidades
(semilla por defecto 7; use `SEMILLA=<n>` para variar). Sirve para probar que su solución no está "aprendida de memoria".
El dataset oficial de la evaluación es el de `datos/csv`.

## Reglas de uso

Datos ficticios, de uso libre dentro del hackatón. No suban a los modelos datos personales reales.
