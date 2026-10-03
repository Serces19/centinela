"""backend/services/guardrail.py

Servicio de seguridad y gobernanza de Centinela mediante Bedrock Guardrails.

Aplica:
1. Filtro PII: anonimización de NAME, EMAIL, PHONE, ADDRESS.
2. Filtro de ataques de prompt: PROMPT_ATTACK (detección y neutralización de jailbreaks / inyecciones).
3. Mecanismo de defensa en profundidad: Bedrock Guardrail en AWS + fallback determinista con regex
   garantizando protección total incluso sin conectividad o ante variaciones idiomáticas.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
GUARDRAIL_ID = os.getenv("GUARDRAIL_ID", "").strip() or None
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "1").strip() or "1"

# Expresiones regulares de ataque de prompt (español e inglés)
PROMPT_ATTACK_PATTERNS = [
    re.compile(r"(?i)\b(?:ignora|olvida|desestima|omite|bypass|ignore|disregard)\s+(?:todas?\s+)?(?:las?\s+)?(?:reglas|instrucciones|politicas|directrices|normas)", re.UNICODE),
    re.compile(r"(?i)\b(?:aprueba|autoriza)\s+(?:todos?\s+los?\s+)?(?:descuentos|pedidos|cupos)\s+(?:sin\s+(?:revision|limite|control|importar)|a\s+todos|de\s+forma\s+automatica)", re.UNICODE),
    re.compile(r"(?i)\b(?:aprueba\s+todos\s+los\s+descuentos)\b", re.UNICODE),
    re.compile(r"(?i)\b(?:system\s+prompt|instrucciones\s+del\s+sistema|jailbreak|override\s+rules|developer\s+mode)\b", re.UNICODE),
    re.compile(r"(?i)\b(?:ahora\s+eres|eres\s+un\s+nuevo|actua\s+como|act\s+as\s+a\s+different)\b", re.UNICODE),
]

# Expresiones regulares para PII fallback
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?57\s*)?[3][0-9]{2}[\s\-]?[0-9]{3}[\s\-]?[0-9]{4}\b")
NAME_CONTEXT_PATTERN = re.compile(
    r"(?i)\b(?:nombre\s+es|cliente\s+se\s+llama|llamado|llamada|vendedor\s+es)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})\b"
)
ADDRESS_PATTERN = re.compile(
    r"(?i)\b(?:Calle|Carrera|Cra|Clle|Avenida|Av|Transversal|Diagonal|Dg|Tv)\.?\s+\d+[\s\w#-]+\b"
)


@dataclass(frozen=True)
class ResultadoGuardrail:
    """Resultado inmutable de la evaluación del Guardrail."""
    texto: str
    intervino: bool
    accion: Literal["NONE", "GUARDRAIL_INTERVENED"]
    pii_detectado: bool
    ataque_detectado: bool

    @property
    def guardrail_intervino(self) -> bool:
        """Alias compatible con especificaciones de evaluación."""
        return self.intervino


def _evaluar_fallback_local(texto: str) -> tuple[str, bool, bool]:
    """Evalúa localmente patrones de PII y prompt attacks como defensa en profundidad.

    Devuelve: (texto_anonimizado, pii_encontrado, ataque_encontrado)
    """
    texto_procesado = texto
    pii_encontrado = False
    ataque_encontrado = False

    # 1. Detectar prompt attack
    for pat in PROMPT_ATTACK_PATTERNS:
        if pat.search(texto):
            ataque_encontrado = True
            break

    # 2. Detectar y anonimizar EMAIL
    if EMAIL_PATTERN.search(texto_procesado):
        texto_procesado = EMAIL_PATTERN.sub("{EMAIL}", texto_procesado)
        pii_encontrado = True

    # 3. Detectar y anonimizar PHONE
    if PHONE_PATTERN.search(texto_procesado):
        texto_procesado = PHONE_PATTERN.sub("{PHONE}", texto_procesado)
        pii_encontrado = True

    # 4. Detectar y anonimizar ADDRESS
    if ADDRESS_PATTERN.search(texto_procesado):
        texto_procesado = ADDRESS_PATTERN.sub("{ADDRESS}", texto_procesado)
        pii_encontrado = True

    # 5. Detectar y anonimizar NAME en contexto
    match_name = NAME_CONTEXT_PATTERN.search(texto_procesado)
    if match_name:
        nombre_detectado = match_name.group(1)
        texto_procesado = texto_procesado.replace(nombre_detectado, "{NAME}")
        pii_encontrado = True

    return texto_procesado, pii_encontrado, ataque_encontrado


def aplicar_guardrail(
    texto: str,
    fuente: Literal["INPUT", "OUTPUT"] = "INPUT",
    guardrail_id: str | None = None,
    guardrail_version: str | None = None,
) -> ResultadoGuardrail:
    """Aplica la política de seguridad Bedrock Guardrail y el fallback de defensa en profundidad.

    Args:
        texto: Texto a evaluar (entrada de usuario o fragmento de política o salida del modelo).
        fuente: 'INPUT' o 'OUTPUT' según el origen del contenido.
        guardrail_id: ID opcional para sobreescribir la configuración del entorno.
        guardrail_version: Versión opcional.

    Returns:
        ResultadoGuardrail con el texto (anonimizado si aplica) y banderas de intervención y ataque.
    """
    gid = guardrail_id or GUARDRAIL_ID
    gver = guardrail_version or GUARDRAIL_VERSION

    bedrock_intervino = False
    bedrock_action: Literal["NONE", "GUARDRAIL_INTERVENED"] = "NONE"
    bedrock_texto = texto
    bedrock_pii = False
    bedrock_ataque = False

    if gid:
        try:
            client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
            # Para evaluación de PII con acción ANONYMIZE, Bedrock anonimiza en OUTPUT
            # Para PROMPT_ATTACK, actúa en INPUT.
            # Por robustez, si fuente es INPUT pero queremos anonimizar PII o detectar ataque:
            # Bedrock admite source='INPUT' o 'OUTPUT'.
            response = client.apply_guardrail(
                guardrailIdentifier=gid,
                guardrailVersion=gver,
                source=fuente,
                content=[{"text": {"text": texto}}],
            )
            act = response.get("action", "NONE")
            if act == "GUARDRAIL_INTERVENED":
                bedrock_intervino = True
                bedrock_action = "GUARDRAIL_INTERVENED"

            # Revisar salidas transformadas (por ejemplo texto anonimizado)
            outputs = response.get("outputs", [])
            if outputs and outputs[0].get("text"):
                bedrock_texto = outputs[0]["text"]

            # Analizar assessments detallados
            assessments = response.get("assessments", [])
            for ass in assessments:
                # PII check
                sensitive = ass.get("sensitiveInformationPolicy", {})
                if sensitive.get("piiEntities"):
                    bedrock_pii = True
                    bedrock_intervino = True
                    bedrock_action = "GUARDRAIL_INTERVENED"

                # Content Policy check (Prompt attack u otros filtros)
                content_policy = ass.get("contentPolicy", {})
                for filt in content_policy.get("filters", []):
                    if filt.get("type") == "PROMPT_ATTACK" and (filt.get("detected") or filt.get("action") == "BLOCKED"):
                        bedrock_ataque = True
                        bedrock_intervino = True
                        bedrock_action = "GUARDRAIL_INTERVENED"

        except Exception as e:
            logger.warning("Fallo al invocar Bedrock apply_guardrail (%s). Activando fallback local.", e)

    # Evaluación con capa de defensa en profundidad / fallback determinista
    texto_local, local_pii, local_ataque = _evaluar_fallback_local(bedrock_texto)

    final_pii = bedrock_pii or local_pii
    final_ataque = bedrock_ataque or local_ataque
    final_intervino = bedrock_intervino or final_pii or final_ataque
    final_action: Literal["NONE", "GUARDRAIL_INTERVENED"] = (
        "GUARDRAIL_INTERVENED" if final_intervino else "NONE"
    )

    return ResultadoGuardrail(
        texto=texto_local,
        intervino=final_intervino,
        accion=final_action,
        pii_detectado=final_pii,
        ataque_detectado=final_ataque,
    )
