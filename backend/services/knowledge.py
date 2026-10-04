"""backend/services/knowledge.py

Recuperación de políticas corporativas desde la Bedrock Knowledge Base de Centinela (un solo camino).

- Consulta `bedrock-agent-runtime:retrieve` sobre la KB `centinela-politicas-kb` (S3 + S3 Vectors + Titan V2).
- El documento (FIN-POL-004, COM-POL-002, OPE-POL-007) se deduce de la URI del objeto en S3, nunca del texto.
- Se descartan resultados que no provengan de las tres políticas oficiales (defensa contra índices contaminados)
  y fragmentos duplicados.
- La sección se identifica por los encabezados conocidos de cada política.
- Si la KB no está configurada o falla, no se inventa nada: se devuelve una lista vacía y el agente responde
  "no tengo evidencia suficiente".
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata

import boto3

from contracts.herramientas import FragmentoPolitica

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "").strip() or None

# Encabezados numerados de cada política (índice de secciones para citar con precisión).
SECCIONES: dict[str, dict[int, str]] = {
    "FIN-POL-004": {
        1: "Objetivo",
        2: "Plazos de pago por segmento",
        3: "Cupo de crédito",
        4: "Seguimiento y escalamiento",
        5: "Señales de alerta temprana",
        6: "Comunicación con el cliente",
    },
    "COM-POL-002": {
        1: "Objetivo",
        2: "Topes de descuento por segmento",
        3: "Aprobación especial",
        4: "Prohibiciones",
        5: "Monitoreo",
    },
    "OPE-POL-007": {
        1: "Objetivo",
        2: "Cobertura mínima",
        3: "Proveedores",
        4: "Revisión de precios",
    },
}


def calcular_hash_sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _norm(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_tildes.lower())


def documento_desde_uri(uri: str) -> str | None:
    """Código de la política según el nombre del objeto S3 (p. ej. `.../FIN-POL-004_politica_credito.pdf`)."""
    nombre = uri.rsplit("/", 1)[-1]
    return next((codigo for codigo in SECCIONES if codigo in nombre), None)


def seccion_del_fragmento(documento: str, texto: str) -> str:
    """Secciones de la política que contiene el fragmento, por sus encabezados (máx. 60 caracteres)."""
    t = _norm(texto)
    presentes = sorted(n for n, titulo in SECCIONES[documento].items() if re.search(rf"\b{n}\.\s*{re.escape(_norm(titulo))}", t))
    if not presentes:
        return f"{documento}"
    if len(presentes) == 1:
        n = presentes[0]
        return f"{documento} §{n} {SECCIONES[documento][n]}"[:60]
    return f"{documento} §{presentes[0]}-§{presentes[-1]}"[:60]


class PoliticasRetriever:
    """Recuperador de políticas sobre la Knowledge Base de Centinela."""

    def __init__(self, region_name: str = AWS_REGION, knowledge_base_id: str | None = KNOWLEDGE_BASE_ID) -> None:
        self.region_name = region_name
        self.knowledge_base_id = knowledge_base_id
        self._cliente = None

    def _runtime(self):
        if self._cliente is None:
            self._cliente = boto3.client("bedrock-agent-runtime", region_name=self.region_name)
        return self._cliente

    def buscar(self, consulta: str, k: int = 3) -> list[FragmentoPolitica]:
        """Hasta `k` fragmentos de las políticas oficiales, sin duplicados, más relevantes primero."""
        k = max(1, min(5, k))
        if not self.knowledge_base_id:
            logger.error("KNOWLEDGE_BASE_ID no está configurado: no hay políticas que consultar.")
            return []
        try:
            respuesta = self._runtime().retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={"text": consulta},
                retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": min(10, k * 2)}},
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Falla en bedrock-agent-runtime:retrieve: %s", e)
            return []

        vistos: set[str] = set()
        fragmentos: list[FragmentoPolitica] = []
        for r in respuesta.get("retrievalResults", []):
            uri = r.get("location", {}).get("s3Location", {}).get("uri", "")
            documento = documento_desde_uri(uri)
            if documento is None:
                logger.warning("Fragmento descartado: no proviene de una política oficial (%s)", uri)
                continue
            texto = r.get("content", {}).get("text", "").strip()
            huella = calcular_hash_sha256(texto)
            if not texto or huella in vistos:
                continue
            vistos.add(huella)
            fragmentos.append(
                FragmentoPolitica(
                    documento=documento,  # type: ignore[arg-type]
                    seccion=seccion_del_fragmento(documento, texto),
                    texto=texto,
                    score=round(min(1.0, max(0.0, float(r.get("score", 0.0)))), 4),
                    fragmento_hash=huella,
                )
            )
            if len(fragmentos) == k:
                break
        return fragmentos


_default_retriever: PoliticasRetriever | None = None


def get_politicas_retriever() -> PoliticasRetriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = PoliticasRetriever()
    return _default_retriever
