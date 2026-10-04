"""scripts/sync_knowledge_base.py

Inicia y monitorea el trabajo de sincronización / ingestión de los documentos normativos PDF
(FIN-POL-004, COM-POL-002, OPE-POL-007) desde el bucket S3 hacia Amazon Bedrock Knowledge Base
con backend S3 Vectors.
"""

import sys
import time
import boto3

REGION = "us-east-1"
KB_ID = "OGWCO3WVFH"
DATA_SOURCE_ID = "BHCVMHRB2F"

def sync_kb():
    print(f"=== Sincronización Bedrock Knowledge Base ({KB_ID}) ===")
    client = boto3.client("bedrock-agent", region_name=REGION)
    
    # 1. Comprobar estado de la Knowledge Base y Data Source
    try:
        kb_desc = client.get_knowledge_base(knowledgeBaseId=KB_ID)
        print(f"Knowledge Base: {kb_desc['knowledgeBase']['name']} | Estado: {kb_desc['knowledgeBase']['status']}")
        
        ds_desc = client.get_data_source(knowledgeBaseId=KB_ID, dataSourceId=DATA_SOURCE_ID)
        print(f"Data Source: {ds_desc['dataSource']['name']} | Estado: {ds_desc['dataSource']['status']}")
    except Exception as e:
        print(f"Error consultando KB/DataSource: {e}")
        sys.exit(1)
        
    # 2. Iniciar Ingestion Job
    print("\nIniciando Ingestion Job en Bedrock...")
    try:
        job = client.start_ingestion_job(
            knowledgeBaseId=KB_ID,
            dataSourceId=DATA_SOURCE_ID,
            description="Ingestión de políticas normativas Distribuidora Andina SAS",
        )
        job_id = job["ingestionJob"]["ingestionJobId"]
        print(f"Ingestion Job iniciado con ID: {job_id}")
    except Exception as e:
        print(f"Error iniciando Ingestion Job: {e}")
        # Listar si ya había uno corriendo
        jobs = client.list_ingestion_jobs(knowledgeBaseId=KB_ID, dataSourceId=DATA_SOURCE_ID)
        summaries = jobs.get("ingestionJobSummaries", [])
        if summaries:
            job_id = summaries[0]["ingestionJobId"]
            print(f"Usando último trabajo existente: {job_id}")
        else:
            sys.exit(1)

    # 3. Monitorear hasta que termine
    print("Esperando a que la ingestión complete...")
    for _ in range(60):
        res = client.get_ingestion_job(
            knowledgeBaseId=KB_ID,
            dataSourceId=DATA_SOURCE_ID,
            ingestionJobId=job_id,
        )
        status = res["ingestionJob"]["status"]
        stats = res["ingestionJob"].get("statistics", {})
        print(f"  Estado: {status} | Documentos escaneados: {stats.get('numberOfDocumentsScanned', 0)} | Indexados: {stats.get('numberOfNewDocumentsIndexed', 0)}")
        if status in ("COMPLETE", "FAILED", "STOPPED"):
            break
        time.sleep(5)

    if status != "COMPLETE":
        print(f"Advertencia: El job terminó con estado {status}")
        reasons = res["ingestionJob"].get("failureReasons", [])
        if reasons:
            print("Razones de falla:", reasons)
    else:
        print("\n ¡Ingestión completada con éxito en Bedrock S3 Vectors!")

    # 4. Probar búsqueda en Bedrock Agent Runtime
    print("\nProbando búsqueda semántica con bedrock-agent-runtime.retrieve()...")
    runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)
    query = "Cuál es el plazo de pago para clientes mayoristas según la política?"
    try:
        retrieval = runtime.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": 2,
                }
            },
        )
        results = retrieval.get("retrievalResults", [])
        print(f"Resultados obtenidos: {len(results)}")
        for i, r in enumerate(results, 1):
            score = r.get("score", "N/A")
            text = r.get("content", {}).get("text", "")[:200]
            print(f"  [{i}] Score: {score}")
            print(f"      Texto: {text}...")
    except Exception as e:
        print(f"Error en retrieve: {e}")

if __name__ == "__main__":
    sync_kb()
