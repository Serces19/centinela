"""Crea el bucket de vectores e índice propios de Centinela en S3 Vectors (idempotente).

La Knowledge Base de Centinela NO debe compartir índice con otros proyectos: una consulta devolvería
fragmentos de documentos ajenos. Este script crea:
  - vector bucket  centinela-vectors-<cuenta>
  - índice         politicas  (1024 dimensiones, float32, distancia coseno)

Imprime el ARN del índice para `infra/kb.tf` (variable `s3_vectors_index_arn`).
"""

import sys

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
INDICE = "politicas"
DIMENSION = 1024   # Titan Text Embeddings V2


def main() -> int:
    cuenta = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    bucket = f"centinela-vectors-{cuenta}"
    s3v = boto3.client("s3vectors", region_name=REGION)

    try:
        s3v.create_vector_bucket(vectorBucketName=bucket)
        print(f"[OK] Vector bucket creado: {bucket}")
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("ConflictException", "VectorBucketAlreadyExists"):
            raise
        print(f"[OK] El vector bucket ya existe: {bucket}")

    try:
        s3v.create_index(
            vectorBucketName=bucket,
            indexName=INDICE,
            dataType="float32",
            dimension=DIMENSION,
            distanceMetric="cosine",
            # Bedrock guarda el texto del fragmento como metadato; debe ser no filtrable (límite de tamaño)
            metadataConfiguration={"nonFilterableMetadataKeys": ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]},
        )
        print(f"[OK] Índice creado: {INDICE}")
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("ConflictException", "IndexAlreadyExists"):
            raise
        print(f"[OK] El índice ya existe: {INDICE}")

    info = s3v.get_index(vectorBucketName=bucket, indexName=INDICE)["index"]
    print(f"INDEX_ARN={info['indexArn']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
