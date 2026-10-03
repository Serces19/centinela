# scripts/deploy_backend.py
"""Automatización del empaquetado, construcción de contenedor Docker y despliegue a AWS Lambda.

Flujo:
1. Obtiene credenciales de autenticación para AWS ECR.
2. Construye la imagen Docker centinela-backend:latest desde backend/.
3. Etiqueta y sube la imagen al repositorio ECR de la cuenta 295894327291.
4. Actualiza el código de la función Lambda 'centinela-backend'.
5. Espera a que la actualización de la función se complete y verifica el endpoint /health.
"""

import base64
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import boto3

REGION = "us-east-1"
ACCOUNT_ID = "295894327291"
REPO_NAME = "centinela-backend"
FUNCTION_NAME = "centinela-backend"
IMAGE_URI = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{REPO_NAME}:latest"


def run(cmd: str, cwd: str | None = None):
    print(f"-> Ejecutando: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error ({res.returncode}):\n{res.stderr}\n{res.stdout}")
        sys.exit(res.returncode)
    return res.stdout


def main():
    root = Path(__file__).resolve().parent.parent
    backend_dir = root / "backend"

    print("=== Despliegue de Backend Centinela a AWS Lambda ===")

    # 1. Autenticación con ECR
    print("[1/5] Autenticando Docker con Amazon ECR...")
    ecr_client = boto3.client("ecr", region_name=REGION)
    token_resp = ecr_client.get_authorization_token()
    auth_data = token_resp["authorizationData"][0]
    token = base64.b64decode(auth_data["authorizationToken"]).decode("utf-8")
    username, password = token.split(":")
    endpoint = auth_data["proxyEndpoint"]

    login_cmd = f"docker login -u {username} -p {password} {endpoint}"
    run(login_cmd)
    print("   Docker autenticado exitosamente.")

    # 2. Build de Docker
    print(f"[2/5] Construyendo imagen Docker {IMAGE_URI}...")
    run(f"docker build -t {IMAGE_URI} .", cwd=str(backend_dir))
    print("   Imagen construida exitosamente.")

    # 3. Push a ECR
    print(f"[3/5] Subiendo imagen a ECR ({IMAGE_URI})...")
    run(f"docker push {IMAGE_URI}")
    print("   Imagen subida exitosamente.")

    # 4. Actualizar función Lambda
    print(f"[4/5] Actualizando función Lambda '{FUNCTION_NAME}'...")
    lambda_client = boto3.client("lambda", region_name=REGION)
    upd_resp = lambda_client.update_function_code(
        FunctionName=FUNCTION_NAME,
        ImageUri=IMAGE_URI,
    )
    print(f"   Iniciada actualización de Lambda (Status: {upd_resp.get('LastUpdateStatus', 'InProgress')}).")

    # Esperar a que la Lambda termine de actualizar
    print("   Esperando a que la función termine de actualizarse...")
    for _ in range(30):
        fn = lambda_client.get_function(FunctionName=FUNCTION_NAME)
        status = fn["Configuration"].get("LastUpdateStatus")
        if status == "Successful":
            print("   Función actualizada con éxito.")
            break
        elif status == "Failed":
            reason = fn["Configuration"].get("LastUpdateStatusReason")
            print(f"Error actualizando función: {reason}")
            sys.exit(1)
        time.sleep(3)

    # 5. Verificación de Healthcheck en Function URL
    print("[5/5] Verificando Function URL pública...")
    url_config = lambda_client.get_function_url_config(FunctionName=FUNCTION_NAME)
    function_url = url_config["FunctionUrl"]
    health_url = f"{function_url}health"
    print(f"   Consultando {health_url}...")

    time.sleep(2)
    req = urllib.request.Request(health_url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        print(f"   Respuesta: {resp.status} {body}")

    print(f"\n Despliegue de Backend completado exitosamente: {function_url}")


if __name__ == "__main__":
    main()
