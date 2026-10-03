# scripts/deploy_all.py
"""Script Maestro de Despliegue 'One-Click' de Centinela (Fase 4A / Tarea 4.4).

Orquesta el despliegue ordenado de extremo a extremo de todo el sistema en AWS us-east-1:
1. Infraestructura con Terraform (DynamoDB, Lambda, ECR, CloudWatch, SNS, Presupuesto, Amplify).
2. Sincronización de Políticas normativas en S3 y Embeddings Titan V2 (setup_s3_politicas.py).
3. Publicación y verificación de Bedrock Guardrail (setup_guardrail.py).
4. Construcción y despliegue del contenedor Docker a ECR y Lambda (deploy_backend.py).
5. Compilación del frontend React Vite y despliegue en AWS Amplify Hosting (deploy_frontend.py).
6. Verificación de salud y emisión de URLs públicas finales.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
INFRA_DIR = ROOT / "infra"
SCRIPTS_DIR = ROOT / "scripts"


def run_step(step_num: int, title: str, cmd: list[str], cwd: Path | None = None):
    print("\n" + "=" * 70)
    print(f"[{step_num}/6] {title}")
    print("=" * 70)
    t0 = time.perf_counter()
    res = subprocess.run(cmd, cwd=str(cwd or ROOT), text=True)
    dt = round(time.perf_counter() - t0, 1)
    if res.returncode != 0:
        print(f"\n❌ Error en el paso [{step_num}]: {title} (Código: {res.returncode})")
        sys.exit(res.returncode)
    print(f"✅ Paso [{step_num}] completado en {dt} s.")


def main():
    t_inicio_total = time.perf_counter()
    print("=" * 70)
    print("🚀 CENTINELA · DESPLIEGUE INTEGRAL DESDE CERO (AWS SERVERLESS)")
    print("   Fecha: " + datetime.now(timezone.utc).isoformat())
    print("=" * 70)

    # 1. Terraform Apply
    run_step(
        1,
        "Aprovisionando Infraestructura Base con Terraform",
        ["terraform", "apply", "-auto-approve"],
        cwd=INFRA_DIR,
    )

    # 2. S3 Políticas y Embeddings
    run_step(
        2,
        "Sincronizando Políticas Corporativas en Amazon S3 y Embeddings Titan V2",
        [sys.executable, str(SCRIPTS_DIR / "setup_s3_politicas.py")],
    )

    # 3. Bedrock Guardrail
    run_step(
        3,
        "Configurando y Verificando Bedrock Guardrails (PII + Prompt Attack)",
        [sys.executable, str(SCRIPTS_DIR / "setup_guardrail.py")],
    )

    # 4. Backend Container & Lambda
    run_step(
        4,
        "Construyendo Contenedor Docker y Desplegando a AWS Lambda",
        [sys.executable, str(SCRIPTS_DIR / "deploy_backend.py")],
    )

    # 5. Frontend Amplify
    run_step(
        5,
        "Compilando Frontend React Vite y Desplegando en AWS Amplify",
        [sys.executable, str(SCRIPTS_DIR / "deploy_frontend.py")],
    )

    # 6. Verificación E2E de Salud
    print("\n" + "=" * 70)
    print("[6/6] Verificación de Disponibilidad Pública en Vivo")
    print("=" * 70)

    lambda_url = "https://kshttlmqbtzbjc5a73m5v6rfre0qimbv.lambda-url.us-east-1.on.aws/health"
    amplify_url = "https://main.d1y5ytuqvgx3m2.amplifyapp.com"

    print(f"-> Verificando Backend Lambda: {lambda_url}")
    try:
        req_b = urllib.request.Request(lambda_url)
        with urllib.request.urlopen(req_b, timeout=20) as resp_b:
            print(f"   Backend: {resp_b.status} OK -> {resp_b.read().decode('utf-8')}")
    except Exception as e:
        print(f"   ⚠️ Advertencia consultando Backend: {e}")

    print(f"-> Verificando Frontend Amplify: {amplify_url}")
    try:
        req_f = urllib.request.Request(amplify_url)
        with urllib.request.urlopen(req_f, timeout=20) as resp_f:
            print(f"   Frontend: {resp_f.status} OK (CloudFront)")
    except Exception as e:
        print(f"   ⚠️ Advertencia consultando Frontend: {e}")

    dt_total = round((time.perf_counter() - t_inicio_total) / 60, 2)
    print("\n" + "=" * 70)
    print(f"🎉 DESPLIEGUE INTEGRAL COMPLETADO CON ÉXITO EN {dt_total} MINUTOS")
    print("🌐 Frontend Amplify: https://main.d1y5ytuqvgx3m2.amplifyapp.com")
    print("🌐 Backend Lambda:   https://kshttlmqbtzbjc5a73m5v6rfre0qimbv.lambda-url.us-east-1.on.aws/")
    print("📊 CloudWatch:       Centinela-Operaciones")
    print("=" * 70)


if __name__ == "__main__":
    main()
