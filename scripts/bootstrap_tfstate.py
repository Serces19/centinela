"""Script de bootstrap para backend remoto de Terraform en AWS.

Crea:
1. Bucket S3 versionado y encriptado: `centinela-tfstate-295894327291`
2. Tabla DynamoDB de bloqueo: `centinela-tfstate-locks`
"""

import sys
import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
ACCOUNT_ID = "295894327291"
BUCKET_NAME = f"centinela-tfstate-{ACCOUNT_ID}"
TABLE_NAME = "centinela-tfstate-locks"


def bootstrap():
    session = boto3.Session(region_name=REGION)
    s3 = session.client("s3")
    dynamodb = session.client("dynamodb")

    print(f"[*] Verificando/creando bucket S3: {BUCKET_NAME} en {REGION}...")
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"[OK] Bucket {BUCKET_NAME} ya existe.")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code in ("404", "NoSuchBucket"):
            print(f"[*] Creando bucket {BUCKET_NAME}...")
            # En us-east-1 no se pasa CreateBucketConfiguration
            s3.create_bucket(Bucket=BUCKET_NAME)
            print(f"[OK] Bucket {BUCKET_NAME} creado.")
        else:
            print(f"[!] Error al verificar bucket: {e}")
            raise

    # 1. Versionado
    print(f"[*] Habilitando versionado en {BUCKET_NAME}...")
    s3.put_bucket_versioning(
        Bucket=BUCKET_NAME,
        VersioningConfiguration={"Status": "Enabled"},
    )

    # 2. Encriptación por defecto
    print(f"[*] Configurando encriptacion AES256 por defecto en {BUCKET_NAME}...")
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

    # 3. Bloqueo de acceso publico
    print(f"[*] Aplicando bloqueo de acceso publico en {BUCKET_NAME}...")
    s3.put_public_access_block(
        Bucket=BUCKET_NAME,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    print(f"[OK] Bucket {BUCKET_NAME} configurado correctamente.")

    # 4. Tabla DynamoDB de locks
    print(f"[*] Verificando/creando tabla DynamoDB: {TABLE_NAME}...")
    try:
        dynamodb.describe_table(TableName=TABLE_NAME)
        print(f"[OK] Tabla {TABLE_NAME} ya existe.")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "ResourceNotFoundException":
            print(f"[*] Creando tabla DynamoDB {TABLE_NAME}...")
            dynamodb.create_table(
                TableName=TABLE_NAME,
                KeySchema=[{"AttributeName": "LockID", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "LockID", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
                Tags=[{"Key": "Proyecto", "Value": "centinela"}],
            )
            waiter = dynamodb.get_waiter("table_exists")
            print(f"[*] Esperando activacion de tabla {TABLE_NAME}...")
            waiter.wait(TableName=TABLE_NAME)
            print(f"[OK] Tabla {TABLE_NAME} activa.")
        else:
            print(f"[!] Error al verificar tabla: {e}")
            raise

    print("\n[OK] Bootstrap de Terraform completado con exito.")


if __name__ == "__main__":
    try:
        bootstrap()
    except Exception as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)
