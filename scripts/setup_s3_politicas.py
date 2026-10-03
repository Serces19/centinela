"""Script de aprovisionamiento del bucket S3 de politicas de Centinela.

Crea o asegura el bucket S3 versionado y cifrado con AES256:
centinela-politicas-295894327291 en us-east-1, y sube los 3 PDFs normativos.
"""

import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
BUCKET_NAME = "centinela-politicas-295894327291"

POLITICAS_MAP = {
    "Politica_Credito_y_Cartera.pdf": [
        "FIN-POL-004_politica_credito_cartera.pdf",
        "Politica_Credito_y_Cartera.pdf",
    ],
    "Politica_Descuentos_Comerciales.pdf": [
        "COM-POL-002_politica_descuentos.pdf",
        "Politica_Descuentos_Comerciales.pdf",
    ],
    "Politica_Inventario_y_Precios.pdf": [
        "OPE-POL-007_politica_inventarios_precios.pdf",
        "Politica_Inventario_y_Precios.pdf",
    ],
}


def setup_s3_politicas() -> bool:
    print(f"[*] Conectando a S3 en {REGION} para gestionar bucket {BUCKET_NAME}...")
    s3 = boto3.client("s3", region_name=REGION)

    # 1. Verificar o crear bucket
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"[OK] El bucket {BUCKET_NAME} ya existe.")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code in ("404", "NoSuchBucket"):
            print(f"[*] Creando bucket {BUCKET_NAME} en {REGION}...")
            # En us-east-1 no se pasa CreateBucketConfiguration
            s3.create_bucket(Bucket=BUCKET_NAME)
            print(f"[OK] Bucket {BUCKET_NAME} creado exitosamente.")
        else:
            print(f"[ERROR] Error al verificar bucket {BUCKET_NAME}: {e}", file=sys.stderr)
            return False

    # 2. Configurar cifrado AES256 por defecto
    try:
        s3.put_bucket_encryption(
            Bucket=BUCKET_NAME,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            },
        )
        print("[OK] Cifrado AES256 configurado en el bucket.")
    except ClientError as e:
        print(f"[WARN] No se pudo configurar cifrado: {e}")

    # 3. Configurar versionamiento
    try:
        s3.put_bucket_versioning(
            Bucket=BUCKET_NAME,
            VersioningConfiguration={"Status": "Enabled"},
        )
        print("[OK] Versionamiento activado en el bucket.")
    except ClientError as e:
        print(f"[WARN] No se pudo activar versionamiento: {e}")

    # 4. Subir los archivos PDF
    repo_root = Path(__file__).resolve().parent.parent
    politicas_dir = repo_root / "Kit_Equipos" / "politicas"

    if not politicas_dir.exists():
        print(f"[ERROR] Directorio de politicas no encontrado: {politicas_dir}", file=sys.stderr)
        return False

    archivos_subidos = 0
    for local_name, s3_keys in POLITICAS_MAP.items():
        pdf_path = politicas_dir / local_name
        if not pdf_path.exists():
            print(f"[WARN] Archivo local no encontrado: {pdf_path}")
            continue

        for key in s3_keys:
            print(f"[*] Subiendo {local_name} -> s3://{BUCKET_NAME}/{key}...")
            s3.upload_file(
                Filename=str(pdf_path),
                Bucket=BUCKET_NAME,
                Key=key,
                ExtraArgs={"ContentType": "application/pdf"},
            )
            archivos_subidos += 1
            print(f"[OK] Subido s3://{BUCKET_NAME}/{key}")

    print(f"[OK] Total de objetos subidos a S3: {archivos_subidos}")
    return True


if __name__ == "__main__":
    exito = setup_s3_politicas()
    if not exito:
        sys.exit(1)
