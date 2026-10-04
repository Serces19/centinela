"""Configuración común de pruebas: la autenticación por API key se prueba aparte (test_auth.py)."""
import os

os.environ.setdefault("CENTINELA_AUTH_DISABLED", "true")
