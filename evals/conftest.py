"""Configuración común de pruebas.

- Carga `.env` (IDs de KB y guardrail para las pruebas contra AWS).
- La autenticación por API key se prueba aparte (test_auth.py).
- Las pruebas usan persistencia en memoria: nunca escriben en las tablas DynamoDB reales.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

os.environ.setdefault("CENTINELA_AUTH_DISABLED", "true")
os.environ.setdefault("CENTINELA_PERSISTENCIA_BACKEND", "memory")
