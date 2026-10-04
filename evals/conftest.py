"""Configuración común de pruebas.

- La autenticación por API key se prueba aparte (test_auth.py).
- Las pruebas usan persistencia en memoria: nunca escriben en las tablas DynamoDB reales.
"""
import os

os.environ.setdefault("CENTINELA_AUTH_DISABLED", "true")
os.environ.setdefault("CENTINELA_PERSISTENCIA_BACKEND", "memory")
