"""scripts/backfill_consultas.py

Regenera y persiste en DynamoDB (centinela_trazas) todas las consultas registradas
referenciadas por las alertas y propuestas existentes en centinela_alertas.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Agregar backend al sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from agents.evidencia import construir_ficha
from agents.playbook import generar_candidatas
from semantic.db import get_duckdb_connection
from services.persistencia import persistencia_service
from services.registro_consultas import consulta_en_cache
from services.umbrales import cargar_umbrales
from tools.impacto import calcular_impacto_economico

def backfill():
    print("=== Backfill de Consultas Registradas hacia DynamoDB ===")
    reloj = persistencia_service.obtener_reloj()
    corte_actual = reloj["corte"]
    alertas = persistencia_service.listar_alertas()
    print(f"Total alertas persistidas encontradas: {len(alertas)}")
    
    propuestas = persistencia_service.obtener_propuestas([a.alerta_id for a in alertas])
    print(f"Total propuestas encontradas: {len(propuestas)}")
    
    # Recolectar todos los consulta_ids necesarios
    cids_objetivo = set()
    for a in alertas:
        for h in a.hallazgos:
            cids_objetivo.update(h.consulta_ids)
        p = propuestas.get(a.alerta_id)
        if p:
            if p.diagnostico:
                cids_objetivo.update(c.consulta_id for c in p.diagnostico.cifras)
            cids_objetivo.update(c.consulta_id for c in p.cifras)
            for acc in p.acciones:
                if acc.impacto and acc.impacto.consulta_ids:
                    cids_objetivo.update(acc.impacto.consulta_ids)
                    
    print(f"Total consulta_ids únicos objetivo: {len(cids_objetivo)}")
    print(f"IDs a verificar: {sorted(cids_objetivo)}")
    
    # Ejecutar para cada alerta con propuesta
    umbrales = cargar_umbrales()
    guardadas = 0
    for a in alertas:
        corte = a.hallazgos[0].corte if a.hallazgos else corte_actual
        con = get_duckdb_connection(corte)
        try:
            ficha = construir_ficha(a, corte, con)
            cands = generar_candidatas(a, ficha, umbrales)
            for c in cands:
                calcular_impacto_economico(c.parametros, a, corte, con)
        except Exception as e:
            print(f"Error procesando alerta {a.alerta_id}: {e}")

    # Ahora verificar qué consultas están en caché y persistirlas explícitamente en DynamoDB
    for cid in cids_objetivo:
        c = consulta_en_cache(cid)
        if c is not None:
            persistencia_service.guardar_consulta(c)
            guardadas += 1
            print(f"  [OK] Persistida {cid}: {c.vista} | {c.descripcion[:60]}")
        else:
            # Comprobar si ya estaba en DynamoDB
            existente = persistencia_service.obtener_consulta(cid)
            if existente is not None:
                print(f"  [YA EXISTE] {cid} en DynamoDB")
            else:
                print(f"  [PENDIENTE] {cid} no se pudo regenerar")

    print(f"\nFinalizado. Total consultas guardadas en centinela_trazas: {guardadas}")
    
    # Comprobar específicamente Q-17e9977a073e
    test_cid = "Q-17e9977a073e"
    q_test = persistencia_service.obtener_consulta(test_cid)
    if q_test:
        print(f"\n ÉXITO: {test_cid} ahora existe en DynamoDB:")
        print(f"  SQL: {q_test.sql_renderizado}")
        print(f"  Filas: {q_test.filas}")
        print(f"  Hash: {q_test.resultado_hash}")
    else:
        print(f"\n Error: {test_cid} todavía no se encuentra.")

if __name__ == "__main__":
    backfill()
