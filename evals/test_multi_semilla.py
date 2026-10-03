# evals/test_multi_semilla.py
"""Evaluación de Generalización Multi-Semilla de Centinela (Fase 4B / Tarea 4.5).

Prueba que el Agente Vigía detecta de manera 100% determinista y dinámica los escenarios
sembrados S1-S5 en datasets sintéticos generados con diferentes semillas (SEMILLA=12 y SEMILLA=42),
comprobando que NO existen entidades ni IDs hardcodeados en el código de detección.
"""

from datetime import date
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
import duckdb

from agents.vigia import generar_alertas

ROOT = Path(__file__).resolve().parent.parent
GENERADOR_SCRIPT = ROOT / "Kit_Equipos" / "generador" / "generar_dataset.py"
VIEWS_SQL_PATH = ROOT / "backend" / "semantic" / "views.sql"
REF_CSV_DIR = ROOT / "Kit_Equipos" / "datos" / "csv"


def cargar_dataset_en_duckdb(csv_dir: Path, corte: date) -> duckdb.DuckDBPyConnection:
    """Carga los CSVs generados para una semilla en una base DuckDB en memoria con las 7 vistas."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA IF NOT EXISTS centinela;")
    con.execute("USE centinela;")

    # 1. vendedores
    con.execute(f"""
        CREATE TABLE vendedores AS
        SELECT
            vendedor_id::VARCHAR(4) AS vendedor_id,
            nombre::VARCHAR(100) AS nombre,
            region::VARCHAR(50) AS region
        FROM read_csv_auto('{(csv_dir / 'vendedores.csv').as_posix()}', header=True);
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
        FROM read_csv_auto('{(csv_dir / 'clientes.csv').as_posix()}', header=True);
    """)

    # 3. proveedores
    con.execute(f"""
        CREATE TABLE proveedores AS
        SELECT
            proveedor_id::VARCHAR(4) AS proveedor_id,
            nombre::VARCHAR(100) AS nombre,
            lead_time_dias::INTEGER AS lead_time_dias,
            pais::VARCHAR(50) AS pais
        FROM read_csv_auto('{(csv_dir / 'proveedores.csv').as_posix()}', header=True);
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
        FROM read_csv_auto('{(csv_dir / 'productos.csv').as_posix()}', header=True);
    """)

    # 5. bodegas
    con.execute(f"""
        CREATE TABLE bodegas AS
        SELECT
            bodega_id::VARCHAR(8) AS bodega_id,
            nombre::VARCHAR(100) AS nombre,
            ciudad::VARCHAR(50) AS ciudad
        FROM read_csv_auto('{(csv_dir / 'bodegas.csv').as_posix()}', header=True);
    """)

    # 6. lista_precios
    con.execute(f"""
        CREATE TABLE lista_precios AS
        SELECT
            sku::VARCHAR(6) AS sku,
            fecha_vigencia::DATE AS fecha_vigencia,
            precio_lista::DECIMAL(14,2) AS precio_lista
        FROM read_csv_auto('{(csv_dir / 'lista_precios.csv').as_posix()}', header=True);
    """)

    # 7. costos_proveedor
    con.execute(f"""
        CREATE TABLE costos_proveedor AS
        SELECT
            sku::VARCHAR(6) AS sku,
            proveedor_id::VARCHAR(4) AS proveedor_id,
            fecha_vigencia::DATE AS fecha_vigencia,
            costo_unitario::DECIMAL(14,2) AS costo_unitario
        FROM read_csv_auto('{(csv_dir / 'costos_proveedor.csv').as_posix()}', header=True);
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
        FROM read_csv_auto('{(csv_dir / 'ordenes_compra.csv').as_posix()}', header=True);
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
        FROM read_csv_auto('{(csv_dir / 'pedidos.csv').as_posix()}', header=True);
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
        FROM read_csv_auto('{(csv_dir / 'pedidos_detalle.csv').as_posix()}', header=True);
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
        FROM read_csv_auto('{(csv_dir / 'facturas.csv').as_posix()}', header=True);
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
        FROM read_csv_auto('{(csv_dir / 'pagos.csv').as_posix()}', header=True);
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
        FROM read_csv_auto('{(csv_dir / 'inventario_diario.csv').as_posix()}', header=True);
    """)

    # 14. Tablas de referencia fijas
    con.execute(f"""
        CREATE TABLE ref_topes_descuento AS
        SELECT
            segmento::VARCHAR(50) AS segmento,
            tope_descuento_pct::DECIMAL(5,2) AS tope_descuento_pct
        FROM read_csv_auto('{(REF_CSV_DIR / 'ref_topes_descuento.csv').as_posix()}', header=True);
    """)

    con.execute(f"""
        CREATE TABLE ref_margen_minimo_linea AS
        SELECT
            linea::VARCHAR(50) AS linea,
            margen_minimo_pct::DECIMAL(5,2) AS margen_minimo_pct
        FROM read_csv_auto('{(REF_CSV_DIR / 'ref_margen_minimo_linea.csv').as_posix()}', header=True);
    """)

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

    # Macro de corte y vistas semánticas
    con.execute(f"CREATE OR REPLACE TEMP MACRO fecha_corte() AS DATE '{corte.isoformat()}';")
    views_sql = VIEWS_SQL_PATH.read_text(encoding="utf-8")
    con.execute(views_sql)

    return con


def asegurar_dataset_semilla(semilla: int) -> tuple[Path, dict]:
    """Genera el dataset si no existe y retorna la ruta y el JSON de ground truth."""
    out_dir = ROOT / f"temp_seed_{semilla}"
    escenarios_json = out_dir / "escenarios.json"

    if not escenarios_json.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["SEMILLA"] = str(semilla)
        env["SALIDA"] = str(out_dir)
        env["GUARDAR_ESCENARIOS"] = str(escenarios_json)
        cmd = [sys.executable, str(GENERADOR_SCRIPT)]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert res.returncode == 0, f"Error generando dataset semilla {semilla}:\n{res.stderr}"

    with open(escenarios_json, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    return out_dir, ground_truth


@pytest.mark.parametrize("semilla", [12, 42])
def test_generalizacion_multi_semilla_s1_a_s5(semilla: int):
    """Verifica que Centinela detecta S1 a S5 en una semilla arbitraria."""
    corte = date(2026, 9, 30)
    csv_dir, ground_truth = asegurar_dataset_semilla(semilla)

    con = cargar_dataset_en_duckdb(csv_dir, corte=corte)
    try:
        alertas = generar_alertas(corte=corte, con=con)
        assert len(alertas) > 0, f"No se detectaron alertas para la semilla {semilla}"

        # Recolectar entidades detectadas por huella
        huellas = {a.huella_causa for a in alertas}
        todas_las_entidades = {
            ent.id
            for a in alertas
            for h in a.hallazgos
            for ent in h.entidades
        }

        # 1. S1 (Margen / Costo proveedor)
        s1_prov = ground_truth["s1_proveedor"]
        s1_encontrado = any(h.startswith(f"costo|{s1_prov}") for h in huellas)
        assert s1_encontrado, f"Semilla {semilla}: S1 proveedor {s1_prov} no detectado en huellas {huellas}"

        # 2. S2 (Cartera / Mora cliente)
        s2_cli = ground_truth["s2_cliente"]
        s2_encontrado = any(h.startswith(f"saldo_vencido|{s2_cli}") for h in huellas)
        assert s2_encontrado, f"Semilla {semilla}: S2 cliente {s2_cli} no detectado en huellas {huellas}"

        # 3. S3 (Cobertura / Quiebre inventario)
        s3_sku = ground_truth["s3_sku"]
        s3_encontrado = s3_sku in todas_las_entidades
        assert s3_encontrado, f"Semilla {semilla}: S3 SKU {s3_sku} no detectado en entidades {todas_las_entidades}"

        # 4. S4 (Descuento en exceso vendedor)
        s4_vend = ground_truth["s4_vendedor"]
        s4_encontrado = any(h.startswith(f"descuento_en_exceso|{s4_vend}") for h in huellas)
        assert s4_encontrado, f"Semilla {semilla}: S4 vendedor {s4_vend} no detectado en huellas {huellas}"

        # 5. S5 (Inactividad cliente)
        s5_cli = ground_truth["s5_cliente"]
        s5_encontrado = any(h.startswith(f"veces_intervalo_habitual|{s5_cli}") or h.startswith(f"dias_sin_compra|{s5_cli}") for h in huellas)
        assert s5_encontrado, f"Semilla {semilla}: S5 cliente {s5_cli} no detectado en huellas {huellas}"

        print(f"\n[Semilla {semilla}] 5/5 escenarios detectados dinámicamente:")
        print(f"  - S1 Proveedor: {s1_prov} OK")
        print(f"  - S2 Cliente Mora: {s2_cli} OK")
        print(f"  - S3 SKU Cobertura: {s3_sku} OK")
        print(f"  - S4 Vendedor Descuento: {s4_vend} OK")
        print(f"  - S5 Cliente Inactividad: {s5_cli} OK")

    finally:
        con.close()
