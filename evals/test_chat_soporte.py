# evals/test_chat_soporte.py
"""Pruebas de evaluación para el streaming SSE y Chat de Soporte Anclado (Fase 2G / Handshake H9):

- GET /stream: Emisión de eventos SSE para validación de Lambda Web Adapter.
- POST /chat con streaming SSE:
  - Chat anclado a alerta (contexto de entidades y hallazgos).
  - Consulta con cifras trazables y cierre con ChatFin.
  - Regla 2.18: "No tengo evidencia suficiente" ante consultas no respaldadas.
  - Seguridad Guardrail: Neutralización de ataques de inyección de prompt en el chat.
"""

from datetime import date
import json
import pytest
from fastapi.testclient import TestClient

from agents.vigia import generar_alertas
from api.main import app
from contracts.alertas import Alerta
from contracts.base import EstadoAlerta
from services.persistencia import persistencia_service


@pytest.fixture(autouse=True)
def setup_persistencia():
    """Asegura persistencia limpia en memoria para las pruebas de chat."""
    persistencia_service.use_memory = True
    persistencia_service._mem_alertas.clear()
    persistencia_service._mem_bitacora.clear()
    persistencia_service._mem_trazas.clear()
    persistencia_service._mem_propuestas.clear()
    persistencia_service._mem_resultados.clear()
    persistencia_service._mem_feedback.clear()


@pytest.fixture
def alerta_s1():
    alertas = generar_alertas(date(2026, 8, 15))
    alr = next((a for a in alertas if "PR08" in a.huella_causa), None)
    assert alr is not None
    persistencia_service.guardar_alerta(alr)
    return alr


def parsear_sse_eventos(texto_sse: str) -> list[dict]:
    """Parsea el stream de Server-Sent Events en una lista de diccionarios de eventos."""
    eventos = []
    lineas = texto_sse.strip().split("\n")
    for linea in lineas:
        linea = linea.strip()
        if linea.startswith("data:"):
            payload_str = linea[len("data:"):].strip()
            try:
                eventos.append(json.loads(payload_str))
            except json.JSONDecodeError:
                pass
    return eventos


# =============================================================================
# Prueba 1: Endpoint GET /stream (Lambda Web Adapter SSE)
# =============================================================================