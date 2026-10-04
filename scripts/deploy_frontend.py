#!/usr/bin/env python3
"""Script para automatizar la compilación y despliegue del frontend de Centinela en AWS Amplify.

Flujo:
1. Compila el frontend con `npm run build` en `frontend/`.
2. Empaqueta el contenido de `frontend/dist/` en un archivo `.zip`.
3. Consulta o crea la aplicación en AWS Amplify.
4. Genera la URL de subida mediante `create_deployment`.
5. Sube el `.zip` vía HTTP PUT.
6. Inicia el despliegue con `start_deployment`.
7. Imprime el estado y la URL pública de la aplicación.
"""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

import boto3

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    root_dir = Path(__file__).resolve().parent.parent
    frontend_dir = root_dir / "frontend"
    dist_dir = frontend_dir / "dist"
    zip_path = frontend_dir / "centinela_dist.zip"

    print("=" * 60)
    print("🚀 CENTINELA · Despliegue de Frontend en AWS Amplify")
    print("=" * 60)

    # 1. Compilación
    print(f"\n📦 1. Compilando aplicación en {frontend_dir}...")
    cmd_build = "npm run build"
    # La API key vive en SSM y se incrusta en el build (limitación conocida: queda visible en el bundle).
    import os
    import boto3

    api_key = boto3.client("ssm", region_name="us-east-1").get_parameter(
        Name="/centinela/api_key", WithDecryption=True
    )["Parameter"]["Value"]
    env_build = {**os.environ, "VITE_API_KEY": api_key}
    res = subprocess.run(
        cmd_build,
        cwd=str(frontend_dir),
        shell=True,
        capture_output=True,
        text=True,
        env=env_build,
    )
    if res.returncode != 0:
        print(f"❌ Error en la compilación:\n{res.stderr}\n{res.stdout}")
        sys.exit(1)

    print("✅ Compilación exitosa en dist/")

    # 2. Empaquetado ZIP
    print(f"\n📦 2. Creando archivo zip desde {dist_dir}...")
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in dist_dir.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(dist_dir)
                zipf.write(file, arcname)

    zip_size_kb = round(zip_path.stat().st_size / 1024, 1)
    print(f"✅ Archivo zip creado: {zip_path.name} ({zip_size_kb} KB)")

    # 3. AWS Amplify Deployment
    print("\n☁️  3. Conectando con AWS Amplify...")
    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("amplify", region_name=region)

    app_name = "centinela-frontend"
    branch_name = "main"

    # Buscar la app en Amplify
    apps_resp = client.list_apps()
    app = next((a for a in apps_resp.get("apps", []) if a["name"] == app_name), None)

    if not app:
        print(f"⚠️  La app '{app_name}' no existe en Amplify. Creándola...")
        app_resp = client.create_app(
            name=app_name,
            description="Frontend de Centinela - Vigilancia con IA",
            customRules=[
                {
                    "source": "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json)$)([^.]+$)/>",
                    "target": "/index.html",
                    "status": "200",
                }
            ],
            environmentVariables={
                "VITE_API_URL": "https://kshttlmqbtzbjc5a73m5v6rfre0qimbv.lambda-url.us-east-1.on.aws"
            },
        )
        app = app_resp["app"]
        print(f"✅ App creada con ID: {app['appId']}")

    app_id = app["appId"]
    default_domain = app.get("defaultDomain", f"{app_id}.amplifyapp.com")

    # Verificar o crear branch main
    try:
        client.get_branch(appId=app_id, branchName=branch_name)
    except client.exceptions.NotFoundException:
        print(f"⚠️  Branch '{branch_name}' no existe. Creándolo...")
        client.create_branch(appId=app_id, branchName=branch_name)

    # 4. create-deployment
    print(f"\n📡 4. Creando despliegue para {app_id} (branch: {branch_name})...")
    deployment = client.create_deployment(appId=app_id, branchName=branch_name)
    job_id = deployment["jobId"]
    upload_url = deployment["zipUploadUrl"]
    print(f"✅ Despliegue generado: Job ID {job_id}")

    # 5. Subir zip
    print(f"\n⬆️  5. Subiendo paquete a AWS Amplify...")
    with open(zip_path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(
        upload_url,
        data=data,
        headers={"Content-Type": "application/zip"},
        method="PUT",
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status not in (200, 204):
            print(f"❌ Error al subir ZIP: status {resp.status}")
            sys.exit(1)

    print("✅ Paquete subido exitosamente.")

    # 6. start-deployment
    print(f"\n🚀 6. Iniciando despliegue de la versión en Amplify...")
    client.start_deployment(appId=app_id, branchName=branch_name, jobId=job_id)

    app_url = f"https://{branch_name}.{default_domain}"
    print("\n" + "=" * 60)
    print("🎉 ¡DESPLIEGUE EN AMPLIFY INICIADO CON ÉXITO!")
    print(f"🌐 URL Pública del Frontend: {app_url}")
    print(f"🆔 App ID: {app_id}")
    print(f"🏷️  Job ID: {job_id}")
    print("=" * 60)


if __name__ == "__main__":
    main()
