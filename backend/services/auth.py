# backend/services/auth.py
"""Autenticación mínima por API key (cabecera `x-api-key`).

La clave se lee, en este orden, de:
1. Variable de entorno `CENTINELA_API_KEY` (desarrollo local y pruebas).
2. AWS SSM Parameter Store (`CENTINELA_API_KEY_PARAM`, por defecto `/centinela/api_key`, SecureString).

La autenticación está activa siempre, salvo que se defina `CENTINELA_AUTH_DISABLED=true`
(solo para desarrollo local y pruebas). Si la clave no se puede obtener, la API rechaza
todo (falla cerrada).
"""

from __future__ import annotations

import hmac
import logging
import os
from functools import lru_cache

import boto3

logger = logging.getLogger("centinela.auth")

RUTAS_PUBLICAS = {"/health"}
PARAM_POR_DEFECTO = "/centinela/api_key"


def auth_deshabilitada() -> bool:
    return os.environ.get("CENTINELA_AUTH_DISABLED", "false").strip().lower() == "true"


@lru_cache(maxsize=1)
def _clave_desde_ssm(nombre: str, region: str) -> str | None:
    try:
        ssm = boto3.client("ssm", region_name=region)
        resp = ssm.get_parameter(Name=nombre, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception as e:  # noqa: BLE001 - falla cerrada, se registra y se rechaza
        logger.error("No se pudo leer la API key de SSM (%s): %s", nombre, e)
        return None


def obtener_api_key() -> str | None:
    clave = os.environ.get("CENTINELA_API_KEY", "").strip()
    if clave:
        return clave
    nombre = os.environ.get("CENTINELA_API_KEY_PARAM", PARAM_POR_DEFECTO)
    region = os.environ.get("AWS_REGION", "us-east-1")
    return _clave_desde_ssm(nombre, region)


def clave_valida(recibida: str | None) -> bool:
    """Compara en tiempo constante. Sin clave configurada o sin clave recibida: False."""
    esperada = obtener_api_key()
    if not esperada or not recibida:
        return False
    return hmac.compare_digest(recibida.encode("utf-8"), esperada.encode("utf-8"))
