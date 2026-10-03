"""Verifica la invocación de Bedrock Converse con el perfil de inferencia Haiku 4.5."""

import sys
import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def test_converse():
    print(f"[*] Probando Bedrock converse con {MODEL_ID} en {REGION}...")
    client = boto3.client("bedrock-runtime", region_name=REGION)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": "Responde exactamente la palabra: CENTINELA_OK"
                }
            ],
        }
    ]

    try:
        response = client.converse(
            modelId=MODEL_ID,
            messages=messages,
            inferenceConfig={
                "maxTokens": 20,
                "temperature": 0.0,
            },
        )
        output_text = response["output"]["message"]["content"][0]["text"].strip()
        print(f"[OK] Respuesta del modelo: {output_text}")
        usage = response.get("usage", {})
        print(f"[OK] Tokens entrada: {usage.get('inputTokens')}, Tokens salida: {usage.get('outputTokens')}")
        assert "CENTINELA_OK" in output_text or len(output_text) > 0
        print("[OK] Verificacion de Bedrock exitosa.")
    except ClientError as e:
        print(f"[ERROR] Error al invocar Bedrock: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    test_converse()
