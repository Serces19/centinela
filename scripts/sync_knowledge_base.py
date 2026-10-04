"""Sincroniza las políticas de S3 con la Knowledge Base de Centinela y verifica la recuperación.

Busca la KB por nombre (`centinela-politicas-kb`), lanza el trabajo de ingestión, espera a que termine y
comprueba con 5 consultas que SOLO se recuperan fragmentos de las tres políticas (FIN-POL-004, COM-POL-002,
OPE-POL-007), sin duplicados ni documentos ajenos.
"""

import re
import sys
import time

import boto3

REGION = "us-east-1"
KB_NOMBRE = "centinela-politicas-kb"
CODIGOS = ("FIN-POL-004", "COM-POL-002", "OPE-POL-007")
CONSULTAS = [
    "plazo de pago mayoristas",
    "tope de descuento minoristas",
    "cobertura mínima clase A",
    "costo sube más del 5 %",
    "más de 60 días vencido",
]


def buscar_kb(agente) -> tuple[str, str]:
    for kb in agente.list_knowledge_bases()["knowledgeBaseSummaries"]:
        if kb["name"] == KB_NOMBRE:
            ds = agente.list_data_sources(knowledgeBaseId=kb["knowledgeBaseId"])["dataSourceSummaries"][0]
            return kb["knowledgeBaseId"], ds["dataSourceId"]
    sys.exit(f"No existe la Knowledge Base '{KB_NOMBRE}'. Ejecutar terraform apply.")


def main() -> int:
    agente = boto3.client("bedrock-agent", region_name=REGION)
    runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)
    kb_id, ds_id = buscar_kb(agente)
    print(f"KB {KB_NOMBRE}: {kb_id} · data source {ds_id}")

    job = agente.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)["ingestionJob"]["ingestionJobId"]
    for _ in range(90):
        estado = agente.get_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job)["ingestionJob"]
        print(f"  ingestión: {estado['status']} · {estado.get('statistics', {})}")
        if estado["status"] in ("COMPLETE", "FAILED", "STOPPED"):
            break
        time.sleep(5)
    if estado["status"] != "COMPLETE":
        print("La ingestión no terminó bien:", estado.get("failureReasons"))
        return 1

    errores = 0
    for consulta in CONSULTAS:
        res = runtime.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": consulta},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
        )["retrievalResults"]
        uris = [r["location"]["s3Location"]["uri"].rsplit("/", 1)[-1] for r in res]
        ajenos = [u for u in uris if not any(c in u for c in CODIGOS)]
        textos = [r["content"]["text"] for r in res]
        duplicados = len(textos) - len(set(textos))
        top = re.sub(r"\s+", " ", textos[0])[:70] if textos else "-"
        print(f"- {consulta!r}: {len(res)} fragmentos · ajenos={ajenos} · duplicados={duplicados} · top: {top}")
        errores += bool(ajenos) + bool(duplicados) + (not res)
    print("OK: solo políticas de Centinela, sin duplicados" if not errores else f"FALLÓ: {errores} problema(s)")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
