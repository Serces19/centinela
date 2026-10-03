"""Construye backend/semantic/centinela.duckdb a partir de los 15 CSVs oficiales."""

from pathlib import Path
import sys
import duckdb

ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / "Kit_Equipos" / "datos" / "csv"
TARGET_DB = ROOT / "backend" / "semantic" / "centinela.duckdb"

# Conteos esperados según Kit_Equipos/README.md
CONTEOS_ESPERADOS = {
    "vendedores": 25,
    "clientes": 500,
    "proveedores": 40,
    "productos": 200,
    "bodegas": 2,
    "lista_precios": 400,
    "costos_proveedor": 2404,
    "ordenes_compra": 3802,
    "pedidos": 20013,
    "pedidos_detalle": 60103,
    "facturas": 19085,
    "pagos": 17010,
    "inventario_diario": 146000,
    "ref_topes_descuento": 4,
    "ref_margen_minimo_linea": 7,
}


def build_duckdb():
    print(f"[*] Construyendo DuckDB en: {TARGET_DB}")
    TARGET_DB.parent.mkdir(parents=True, exist_ok=True)

    if TARGET_DB.exists():
        TARGET_DB.unlink()

    con = duckdb.connect(str(TARGET_DB))

    # Esquema centinela
    con.execute("CREATE SCHEMA IF NOT EXISTS centinela;")
    con.execute("USE centinela;")

    # 1. vendedores
    con.execute(f"""
        CREATE TABLE vendedores AS
        SELECT
            vendedor_id::VARCHAR(4) AS vendedor_id,
            nombre::VARCHAR(100) AS nombre,
            region::VARCHAR(50) AS region
        FROM read_csv_auto('{(CSV_DIR / 'vendedores.csv').as_posix()}', header=True);
    """)

    # 2. clientes
    con.execute(f"""
        CREATE TABLE clientes AS
        SELECT
            cliente_id::VARCHAR(6) AS cliente_id,
            nombre::VARCHAR(100) AS nombre,
            segmento::VARCHAR(50) AS segmento,
            ciudad::VARCHAR(50) AS ciudad,
            region::VARCHAR(50) AS region,
            vendedor_id::VARCHAR(4) AS vendedor_id,
            plazo_dias::INTEGER AS plazo_dias,
            cupo_credito::BIGINT AS cupo_credito,
            fecha_alta::DATE AS fecha_alta
        FROM read_csv_auto('{(CSV_DIR / 'clientes.csv').as_posix()}', header=True);
    """)

    # 3. proveedores
    con.execute(f"""
        CREATE TABLE proveedores AS
        SELECT
            proveedor_id::VARCHAR(4) AS proveedor_id,
            nombre::VARCHAR(100) AS nombre,
            lead_time_dias::INTEGER AS lead_time_dias,
            pais::VARCHAR(50) AS pais
        FROM read_csv_auto('{(CSV_DIR / 'proveedores.csv').as_posix()}', header=True);
    """)

    # 4. productos
    con.execute(f"""
        CREATE TABLE productos AS
        SELECT
            sku::VARCHAR(6) AS sku,
            nombre::VARCHAR(100) AS nombre,
            linea::VARCHAR(50) AS linea,
            proveedor_id::VARCHAR(4) AS proveedor_id,
            clase_abc::VARCHAR(1) AS clase_abc,
            unidad::VARCHAR(4) AS unidad
        FROM read_csv_auto('{(CSV_DIR / 'productos.csv').as_posix()}', header=True);
    """)

    # 5. bodegas
    con.execute(f"""
        CREATE TABLE bodegas AS
        SELECT
            bodega_id::VARCHAR(8) AS bodega_id,
            nombre::VARCHAR(100) AS nombre,
            ciudad::VARCHAR(50) AS ciudad
        FROM read_csv_auto('{(CSV_DIR / 'bodegas.csv').as_posix()}', header=True);
    """)

    # 6. lista_precios
    con.execute(f"""
        CREATE TABLE lista_precios AS
        SELECT
            sku::VARCHAR(6) AS sku,
            fecha_vigencia::DATE AS fecha_vigencia,
            precio_lista::DECIMAL(14,2) AS precio_lista
        FROM read_csv_auto('{(CSV_DIR / 'lista_precios.csv').as_posix()}', header=True);
    """)

    # 7. costos_proveedor
    con.execute(f"""
        CREATE TABLE costos_proveedor AS
        SELECT
            sku::VARCHAR(6) AS sku,
            proveedor_id::VARCHAR(4) AS proveedor_id,
            fecha_vigencia::DATE AS fecha_vigencia,
            costo_unitario::DECIMAL(14,2) AS costo_unitario
        FROM read_csv_auto('{(CSV_DIR / 'costos_proveedor.csv').as_posix()}', header=True);
    """)

    # 8. ordenes_compra
    con.execute(f"""
        CREATE TABLE ordenes_compra AS
        SELECT
            oc_id::VARCHAR(10) AS oc_id,
            proveedor_id::VARCHAR(4) AS proveedor_id,
            sku::VARCHAR(6) AS sku,
            bodega_id::VARCHAR(8) AS bodega_id,
            fecha_oc::DATE AS fecha_oc,
            fecha_esperada::DATE AS fecha_esperada,
            fecha_recibida::DATE AS fecha_recibida,
            cantidad::INTEGER AS cantidad,
            costo_unitario::DECIMAL(14,2) AS costo_unitario,
            estado::VARCHAR(50) AS estado
        FROM read_csv_auto('{(CSV_DIR / 'ordenes_compra.csv').as_posix()}', header=True);
    """)

    # 9. pedidos
    con.execute(f"""
        CREATE TABLE pedidos AS
        SELECT
            pedido_id::VARCHAR(10) AS pedido_id,
            fecha::DATE AS fecha,
            cliente_id::VARCHAR(6) AS cliente_id,
            vendedor_id::VARCHAR(4) AS vendedor_id,
            ciudad::VARCHAR(50) AS ciudad,
            canal::VARCHAR(50) AS canal,
            estado::VARCHAR(50) AS estado
        FROM read_csv_auto('{(CSV_DIR / 'pedidos.csv').as_posix()}', header=True);
    """)

    # 10. pedidos_detalle
    con.execute(f"""
        CREATE TABLE pedidos_detalle AS
        SELECT
            pedido_id::VARCHAR(10) AS pedido_id,
            linea_n::INTEGER AS linea_n,
            sku::VARCHAR(6) AS sku,
            cantidad::INTEGER AS cantidad,
            precio_lista::DECIMAL(14,2) AS precio_lista,
            precio_unitario::DECIMAL(14,2) AS precio_unitario,
            descuento_pct::DECIMAL(5,2) AS descuento_pct,
            aprobacion_especial::VARCHAR(1) AS aprobacion_especial,
            valor_neto::DECIMAL(16,2) AS valor_neto,
            costo_unitario::DECIMAL(14,2) AS costo_unitario
        FROM read_csv_auto('{(CSV_DIR / 'pedidos_detalle.csv').as_posix()}', header=True);
    """)

    # 11. facturas
    con.execute(f"""
        CREATE TABLE facturas AS
        SELECT
            factura_id::VARCHAR(10) AS factura_id,
            pedido_id::VARCHAR(10) AS pedido_id,
            cliente_id::VARCHAR(6) AS cliente_id,
            fecha_factura::DATE AS fecha_factura,
            fecha_vencimiento::DATE AS fecha_vencimiento,
            valor_neto::DECIMAL(16,2) AS valor_neto,
            iva::DECIMAL(16,2) AS iva,
            valor_total::DECIMAL(16,2) AS valor_total
        FROM read_csv_auto('{(CSV_DIR / 'facturas.csv').as_posix()}', header=True);
    """)

    # 12. pagos
    con.execute(f"""
        CREATE TABLE pagos AS
        SELECT
            pago_id::VARCHAR(10) AS pago_id,
            factura_id::VARCHAR(10) AS factura_id,
            fecha_pago::DATE AS fecha_pago,
            valor::DECIMAL(16,2) AS valor,
            medio_pago::VARCHAR(50) AS medio_pago
        FROM read_csv_auto('{(CSV_DIR / 'pagos.csv').as_posix()}', header=True);
    """)

    # 13. inventario_diario
    con.execute(f"""
        CREATE TABLE inventario_diario AS
        SELECT
            fecha::DATE AS fecha,
            bodega_id::VARCHAR(8) AS bodega_id,
            sku::VARCHAR(6) AS sku,
            existencia_inicial::INTEGER AS existencia_inicial,
            entradas::INTEGER AS entradas,
            salidas::INTEGER AS salidas,
            existencia_final::INTEGER AS existencia_final
        FROM read_csv_auto('{(CSV_DIR / 'inventario_diario.csv').as_posix()}', header=True);
    """)

    # 14. ref_topes_descuento
    con.execute(f"""
        CREATE TABLE ref_topes_descuento AS
        SELECT
            segmento::VARCHAR(50) AS segmento,
            tope_descuento_pct::DECIMAL(5,2) AS tope_descuento_pct
        FROM read_csv_auto('{(CSV_DIR / 'ref_topes_descuento.csv').as_posix()}', header=True);
    """)

    # 15. ref_margen_minimo_linea
    con.execute(f"""
        CREATE TABLE ref_margen_minimo_linea AS
        SELECT
            linea::VARCHAR(50) AS linea,
            margen_minimo_pct::DECIMAL(5,2) AS margen_minimo_pct
        FROM read_csv_auto('{(CSV_DIR / 'ref_margen_minimo_linea.csv').as_posix()}', header=True);
    """)

    # Tabla de referencia para mapeo ciudad -> bodega (resuelve trampa de datos documentada en 1.2.d)
    con.execute("""
        CREATE TABLE ref_ciudad_bodega (
            ciudad VARCHAR(50) PRIMARY KEY,
            bodega_id VARCHAR(8) NOT NULL
        );
        INSERT INTO ref_ciudad_bodega VALUES
            ('Medellín', 'BOD-MDE'),
            ('Pereira', 'BOD-MDE'),
            ('Barranquilla', 'BOD-MDE'),
            ('Cartagena', 'BOD-MDE'),
            ('Bogotá', 'BOD-BOG'),
            ('Bucaramanga', 'BOD-BOG'),
            ('Cali', 'BOD-BOG');
    """)

    print("\n[*] Verificando conteos de filas:")
    errores = []
    for tabla, esperado in CONTEOS_ESPERADOS.items():
        actual = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        coincide = actual == esperado
        simbolo = "[OK]" if coincide else "[FAIL]"
        print(f"  {simbolo} {tabla:25} -> {actual:>8} filas (esperado {esperado:>8})")
        if not coincide:
            errores.append(f"{tabla}: esperado {esperado}, obtenido {actual}")

    con.close()

    if errores:
        print(f"\n[!] Hubo errores en conteos: {errores}", file=sys.stderr)
        sys.exit(1)

    # Verificamos apertura en modo read_only=True
    con_ro = duckdb.connect(str(TARGET_DB), read_only=True)
    con_ro.execute("USE centinela;")
    count = con_ro.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0]
    con_ro.close()
    print(f"\n[OK] Base DuckDB abre exitosamente en read_only=True ({count} pedidos).")
    size_mb = TARGET_DB.stat().st_size / (1024 * 1024)
    print(f"[OK] Peso final de {TARGET_DB.name}: {size_mb:.2f} MB")


if __name__ == "__main__":
    build_duckdb()
