"""R5: la Knowledge Base devuelve solo fragmentos de las 3 políticas oficiales, sin duplicados y bien citados.

Prueba contra la KB real (KNOWLEDGE_BASE_ID en .env). Además verifica sin AWS la detección de documento y sección.
"""

import pytest

from contracts.herramientas import FragmentoPolitica
from services.knowledge import (
    PoliticasRetriever,
    documento_desde_uri,
    get_politicas_retriever,
    seccion_del_fragmento,
)

OFICIALES = {"FIN-POL-004", "COM-POL-002", "OPE-POL-007"}


def test_documento_desde_uri():
    assert documento_desde_uri("s3://b/FIN-POL-004_politica_credito_cartera.pdf") == "FIN-POL-004"
    assert documento_desde_uri("s3://b/OPE-POL-007_x.pdf") == "OPE-POL-007"
    assert documento_desde_uri("s3://b/compendio-2024-2025-15-136.pdf") is None


def test_seccion_por_encabezados():
    texto = "2. Plazos de pago por segmento Segmento Plazo ... 3. Cupo de crédito El cupo de crédito equivale ..."
    assert seccion_del_fragmento("FIN-POL-004", texto) == "FIN-POL-004 §2-§3"
    assert seccion_del_fragmento("COM-POL-002", "5. Monitoreo Control Comercial revisa") == "COM-POL-002 §5 Monitoreo"
    assert seccion_del_fragmento("OPE-POL-007", "sin encabezados") == "OPE-POL-007"


def test_sin_kb_configurada_devuelve_vacio():
    assert PoliticasRetriever(knowledge_base_id=None).buscar("plazo mayoristas") == []


@pytest.fixture(scope="module")
def retriever():
    return get_politicas_retriever()


@pytest.mark.parametrize(
    "consulta,documento,texto_esperado",
    [
        ("plazo de pago mayoristas", "FIN-POL-004", "45"),
        ("tope de descuento minoristas", "COM-POL-002", "10%"),
        ("cobertura mínima clase A", "OPE-POL-007", "10 días"),
        ("costo sube más del 5 %", "OPE-POL-007", "10 días hábiles"),
        ("más de 60 días vencido", "FIN-POL-004", "Bloqueo de despachos"),
    ],
)
def test_recuperacion_correcta_y_solo_politicas(retriever, consulta, documento, texto_esperado):
    resultados = retriever.buscar(consulta, k=5)
    assert resultados, "la KB no devolvió fragmentos"
    assert all(isinstance(f, FragmentoPolitica) for f in resultados)
    assert {f.documento for f in resultados} <= OFICIALES
    assert len({f.fragmento_hash for f in resultados}) == len(resultados), "fragmentos duplicados"
    assert any(f.documento == documento and texto_esperado in f.texto for f in resultados), (
        f"ningún fragmento de {documento} contiene '{texto_esperado}'"
    )
    assert all(len(f.fragmento_hash) == 64 and 0.0 <= f.score <= 1.0 for f in resultados)
