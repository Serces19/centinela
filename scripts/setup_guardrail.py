"""Script para aprovisionar o actualizar el Guardrail centinela-guardrail en AWS Bedrock.

Configura:
- Filtro PII: NAME, EMAIL, PHONE, ADDRESS con accion ANONYMIZE.
- Filtro de ataques de prompt: PROMPT_ATTACK con fuerza HIGH en la entrada.
- Publica version numerada y actualiza .env con GUARDRAIL_ID y GUARDRAIL_VERSION.
"""

import os
import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
GUARDRAIL_NAME = "centinela-guardrail"
DESCRIPTION = "Guardrail de seguridad para Centinela: anonimizacion PII y bloqueo de prompt attacks"

BLOCKED_INPUT_MSG = "Contenido bloqueado por politicas de seguridad de Centinela."
BLOCKED_OUTPUT_MSG = "Respuesta bloqueada por politicas de seguridad de Centinela."

PII_CONFIG = [
    {"type": "NAME", "action": "ANONYMIZE"},
    {"type": "EMAIL", "action": "ANONYMIZE"},
    {"type": "PHONE", "action": "ANONYMIZE"},
    {"type": "ADDRESS", "action": "ANONYMIZE"},
]

CONTENT_POLICY_CONFIG = [
    {
        "type": "PROMPT_ATTACK",
        "inputStrength": "HIGH",
        "outputStrength": "NONE",
    }
]


def update_env_file(guardrail_id: str, guardrail_version: str) -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    env_example_path = Path(__file__).resolve().parent.parent / ".env.example"

    # Si .env no existe, partir de .env.example
    if not env_path.exists() and env_example_path.exists():
        content = env_example_path.read_text(encoding="utf-8")
    elif env_path.exists():
        content = env_path.read_text(encoding="utf-8")
    else:
        content = ""

    lines = content.splitlines()
    new_lines = []
    found_id = False
    found_ver = False

    for line in lines:
        if line.startswith("GUARDRAIL_ID="):
            new_lines.append(f"GUARDRAIL_ID={guardrail_id}")
            found_id = True
        elif line.startswith("GUARDRAIL_VERSION="):
            new_lines.append(f"GUARDRAIL_VERSION={guardrail_version}")
            found_ver = True
        else:
            new_lines.append(line)

    if not found_id:
        new_lines.append(f"GUARDRAIL_ID={guardrail_id}")
    if not found_ver:
        new_lines.append(f"GUARDRAIL_VERSION={guardrail_version}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"[OK] Archivo .env actualizado con GUARDRAIL_ID={guardrail_id}, GUARDRAIL_VERSION={guardrail_version}")


def setup_guardrail() -> tuple[str, str]:
    print(f"[*] Conectando a Bedrock en {REGION} para gestionar guardrail '{GUARDRAIL_NAME}'...")
    bedrock = boto3.client("bedrock", region_name=REGION)

    # 1. Buscar si ya existe
    existing_id = None
    try:
        response = bedrock.list_guardrails()
        for g in response.get("guardrails", []):
            if g.get("name") == GUARDRAIL_NAME:
                existing_id = g.get("id")
                print(f"[*] Guardrail existente encontrado: ID={existing_id}")
                break
    except ClientError as e:
        print(f"[ERROR] Error al listar guardrails: {e}", file=sys.stderr)
        raise

    guardrail_id = None
    if existing_id:
        print(f"[*] Actualizando guardrail {existing_id}...")
        try:
            update_res = bedrock.update_guardrail(
                guardrailIdentifier=existing_id,
                name=GUARDRAIL_NAME,
                description=DESCRIPTION,
                sensitiveInformationPolicyConfig={"piiEntitiesConfig": PII_CONFIG},
                contentPolicyConfig={"filtersConfig": CONTENT_POLICY_CONFIG},
                blockedInputMessaging=BLOCKED_INPUT_MSG,
                blockedOutputsMessaging=BLOCKED_OUTPUT_MSG,
            )
            guardrail_id = update_res["guardrailId"]
            print(f"[OK] Guardrail actualizado: {guardrail_id}")
        except ClientError as e:
            print(f"[ERROR] Error al actualizar guardrail: {e}", file=sys.stderr)
            raise
    else:
        print(f"[*] Creando nuevo guardrail '{GUARDRAIL_NAME}'...")
        try:
            create_res = bedrock.create_guardrail(
                name=GUARDRAIL_NAME,
                description=DESCRIPTION,
                sensitiveInformationPolicyConfig={"piiEntitiesConfig": PII_CONFIG},
                contentPolicyConfig={"filtersConfig": CONTENT_POLICY_CONFIG},
                blockedInputMessaging=BLOCKED_INPUT_MSG,
                blockedOutputsMessaging=BLOCKED_OUTPUT_MSG,
            )
            guardrail_id = create_res["guardrailId"]
            print(f"[OK] Guardrail creado: {guardrail_id}")
        except ClientError as e:
            print(f"[ERROR] Error al crear guardrail: {e}", file=sys.stderr)
            raise

    # 2. Publicar version numerada
    print(f"[*] Creando version numerada para guardrail {guardrail_id}...")
    try:
        ver_res = bedrock.create_guardrail_version(
            guardrailIdentifier=guardrail_id,
            description="Version 1 con PII ANONYMIZE y PROMPT_ATTACK HIGH",
        )
        guardrail_version = ver_res.get("version", "1")
        print(f"[OK] Version publicada: {guardrail_version}")
    except ClientError as e:
        print(f"[WARN] Error al publicar version numerada (usando DRAFT): {e}")
        guardrail_version = "DRAFT"

    # 3. Guardar en .env
    update_env_file(guardrail_id, guardrail_version)

    return guardrail_id, guardrail_version


if __name__ == "__main__":
    try:
        gid, gver = setup_guardrail()
        print(f"[EXITO] Guardrail configurado: ID={gid}, VERSION={gver}")
    except Exception as exc:
        print(f"[FALLO] {exc}", file=sys.stderr)
        sys.exit(1)
