"""evals/test_knowledge_base.py

Pruebas de recuperacion semantica de politicas con PoliticasRetriever (Bedrock Titan V2 / Knowledge Base).
Verifica que las 5 preguntas clave del reto devuelvan el documento y la seccion correctos,
con scores validos y hashes SHA-256 inmutables.
"""

import pytest
from services.knowledge import PoliticasRetriever, get_politicas_retriever
from contracts.herramientas import FragmentoPolitica


@pytest.fixture(scope="module")
def retriever():
    return get_politicas_retriever()


def test_retriever_inicializacion(retriever: PoliticasRetriever):
    """Verifica que el retriever cargue el corpus de politicas."""
    assert retriever is not None
    assert len(retriever._embeddings_corpus) == 12


def test_recuperacion_plazo_mayoristas(retriever: PoliticasRetriever):
    """1. 'plazo mayoristas' -> FIN-POL-004 (45 dias en §2)."""
    resultados = retriever.buscar("plazo mayoristas", k=3)
    assert len(resultados) >= 1
    top = resultados[0]
    assert isinstance(top, FragmentoPolitica)
    assert top.documento == "FIN-POL-004"
    assert "§2" in top.seccion
    assert "45 días" in top.texto or "45 dias" in top.texto.lower()
    assert len(top.fragmento_hash) == 64
    assert 0.0 <= top.score <= 1.0


def test_recuperacion_tope_descuento_minoristas(retriever: PoliticasRetriever):
    """2. 'tope descuento minoristas' -> COM-POL-002 (10% en §2)."""
    resultados = retriever.buscar("tope descuento minoristas", k=3)
    assert len(resultados) >= 1
    top = resultados[0]
    assert isinstance(top, FragmentoPolitica)
    assert top.documento == "COM-POL-002"
    assert "§2" in top.seccion
    assert "10%" in top.texto
    assert "Minoristas" in top.texto
    assert len(top.fragmento_hash) == 64


def test_recuperacion_cobertura_minima_clase_a(retriever: PoliticasRetriever):
    """3. 'cobertura mínima clase A' -> OPE-POL-007 (10 dias en §2)."""
    resultados = retriever.buscar("cobertura mínima clase A", k=3)
    assert len(resultados) >= 1
    top = resultados[0]
    assert isinstance(top, FragmentoPolitica)
    assert top.documento == "OPE-POL-007"
    assert "§2" in top.seccion
    assert "10 días" in top.texto or "10 dias" in top.texto.lower()
    assert "Clase A" in top.texto
    assert len(top.fragmento_hash) == 64


def test_recuperacion_costo_sube_mas_del_5_porciento(retriever: PoliticasRetriever):
    """4. 'costo sube más del 5 %' -> OPE-POL-007 (revisar precio en 10 dias habiles en §4)."""
    resultados = retriever.buscar("costo sube más del 5 %", k=3)
    assert len(resultados) >= 1
    top = resultados[0]
    assert isinstance(top, FragmentoPolitica)
    assert top.documento == "OPE-POL-007"
    assert "§4" in top.seccion or "precio" in top.seccion.lower()
    assert "5%" in top.texto
    assert "10" in top.texto  # 10 dias habiles
    assert len(top.fragmento_hash) == 64


def test_recuperacion_mas_de_60_dias_vencido(retriever: PoliticasRetriever):
    """5. 'más de 60 días vencido' -> FIN-POL-004 (bloqueo de despachos en §4)."""
    resultados = retriever.buscar("más de 60 días vencido", k=3)
    assert len(resultados) >= 1
    top = resultados[0]
    assert isinstance(top, FragmentoPolitica)
    assert top.documento == "FIN-POL-004"
    assert "§4" in top.seccion
    assert "Bloqueo de despachos" in top.texto or "bloqueo" in top.texto.lower()
    assert len(top.fragmento_hash) == 64
