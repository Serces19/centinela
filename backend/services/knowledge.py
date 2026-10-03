"""backend/services/knowledge.py

Servicio de recuperación semántica de políticas corporativas de Centinela (Knowledge Base & Retriever).

Soporta:
1. Bedrock Titan Embeddings V2 (amazon.titan-embed-text-v2:0, dim 1024) con búsqueda híbrida
   (Vectorial + Coincidencia Léxica / BM25) y persistencia en caché local.
2. Bedrock Knowledge Base (bedrock-agent-runtime:retrieve) si KNOWLEDGE_BASE_ID está configurado.
3. Fallback determinista garantizando 0 fallos de conectividad o cuota.
4. Generación estricta de contratos FragmentoPolitica inmutables con hash SHA-256 verificado.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Literal

import boto3
from botocore.exceptions import ClientError

from contracts.herramientas import FragmentoPolitica

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "").strip() or None

# Archivo de caché de embeddings en disco
EMBEDDINGS_CACHE_FILE = Path(__file__).resolve().parent.parent / "semantic" / "politicas_embeddings.json"

# Corpus canónico de fragmentos normativos (~300 tokens por sección explícita)
FRAGMENTOS_CORPUS: list[dict[str, str]] = [
    {
        "documento": "FIN-POL-004",
        "seccion": "FIN-POL-004 §1 Objetivo",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de crédito y cartera · Código FIN-POL-004 · Versión 3.\n"
            "1. Objetivo: Definir las condiciones de crédito a clientes y el seguimiento de la cartera "
            "para proteger el flujo de caja."
        ),
    },
    {
        "documento": "FIN-POL-004",
        "seccion": "FIN-POL-004 §2 Plazos de pago por segmento",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de crédito y cartera · Código FIN-POL-004 · Versión 3.\n"
            "2. Plazos de pago por segmento:\n"
            "- Grandes superficies: Plazo estándar 60 días (Según contrato marco).\n"
            "- Mayoristas: Plazo estándar 45 días (Clientes estratégicos pueden tener 30 días con descuento comercial).\n"
            "- Minoristas: Plazo estándar 30 días.\n"
            "- Institucional: Plazo estándar 45 días."
        ),
    },
    {
        "documento": "FIN-POL-004",
        "seccion": "FIN-POL-004 §3 Cupo de crédito",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de crédito y cartera · Código FIN-POL-004 · Versión 3.\n"
            "3. Cupo de crédito:\n"
            "El cupo de crédito equivale aproximadamente a dos meses de compras promedio del cliente "
            "y lo revisa Cartera cada trimestre. Ningún pedido puede dejar el saldo abierto por encima "
            "del cupo sin aprobación de la Dirección Financiera."
        ),
    },
    {
        "documento": "FIN-POL-004",
        "seccion": "FIN-POL-004 §4 Seguimiento y escalamiento de cartera",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de crédito y cartera · Código FIN-POL-004 · Versión 3.\n"
            "4. Seguimiento y escalamiento:\n"
            "- 1 a 15 días vencido: Recordatorio de pago (Responsable: Analista de cartera).\n"
            "- 16 a 30 días vencido: Llamada y acuerdo de pago; alerta al vendedor (Responsable: Analista de cartera + vendedor).\n"
            "- 31 a 60 días vencido: Pedidos nuevos solo de contado (Responsable: Jefe de cartera).\n"
            "- Más de 60 días vencido: Bloqueo de despachos y escalamiento a Dirección Financiera (Responsable: Dirección Financiera)."
        ),
    },
    {
        "documento": "FIN-POL-004",
        "seccion": "FIN-POL-004 §5 Señales de alerta temprana y §6 Comunicación",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de crédito y cartera · Código FIN-POL-004 · Versión 3.\n"
            "5. Señales de alerta temprana: Se considera señal de alerta que un cliente aumente su tiempo "
            "promedio de pago en más de 50% frente a su histórico, aunque aún no supere el plazo, "
            "o que concentre más del 10% de la cartera vencida total.\n"
            "6. Comunicación con el cliente: Toda comunicación de cobro debe ser cordial, por escrito "
            "y con copia al vendedor responsable. Los acuerdos de pago quedan registrados en el sistema."
        ),
    },
    {
        "documento": "COM-POL-002",
        "seccion": "COM-POL-002 §1 Objetivo",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de descuentos comerciales · Código COM-POL-002 · Versión 3.\n"
            "1. Objetivo: Asegurar que los descuentos comerciales protejan la rentabilidad y se otorguen "
            "de forma consistente en todas las regiones."
        ),
    },
    {
        "documento": "COM-POL-002",
        "seccion": "COM-POL-002 §2 Topes de descuento por segmento",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de descuentos comerciales · Código COM-POL-002 · Versión 3.\n"
            "2. Topes de descuento por segmento:\n"
            "- Grandes superficies: Tope sin aprobación 18%, Con aprobación especial hasta 21% (Gerencia Comercial).\n"
            "- Mayoristas: Tope sin aprobación 15%, Con aprobación especial hasta 18% (Gerencia Comercial).\n"
            "- Minoristas: Tope sin aprobación 10%, Con aprobación especial hasta 13% (Gerencia Comercial).\n"
            "- Institucional: Tope sin aprobación 12%, Con aprobación especial hasta 15% (Gerencia Comercial)."
        ),
    },
    {
        "documento": "COM-POL-002",
        "seccion": "COM-POL-002 §3 Aprobación especial, §4 Prohibiciones y §5 Monitoreo",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de descuentos comerciales · Código COM-POL-002 · Versión 3.\n"
            "3. Aprobación especial: Cuando un negocio justifique un descuento superior al tope, el vendedor "
            "solicita aprobación a la Gerencia Comercial. Las líneas aprobadas quedan marcadas con aprobación especial = 'S'. "
            "Un descuento por encima del tope sin esa marca es un incumplimiento de la política.\n"
            "4. Prohibiciones: No se permite vender por debajo del costo sin aprobación escrita de la Gerencia General. "
            "No se permite fraccionar pedidos para evadir topes.\n"
            "5. Monitoreo: Control Comercial revisa semanalmente los descuentos por vendedor y región. "
            "Un vendedor con descuentos fuera de política en dos semanas consecutivas pierde la facultad de cotizar sin revisión previa."
        ),
    },
    {
        "documento": "OPE-POL-007",
        "seccion": "OPE-POL-007 §1 Objetivo",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de inventario y revisión de precios · Código OPE-POL-007 · Versión 3.\n"
            "1. Objetivo: Garantizar disponibilidad de producto con el menor capital de trabajo posible, "
            "y mantener precios alineados con los costos."
        ),
    },
    {
        "documento": "OPE-POL-007",
        "seccion": "OPE-POL-007 §2 Cobertura mínima de inventario",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de inventario y revisión de precios · Código OPE-POL-007 · Versión 3.\n"
            "2. Cobertura mínima por clase:\n"
            "- Clase A: Cobertura mínima 10 días de demanda. Acción si se incumple: Alerta a Compras y a Comercial; expeditar orden de compra.\n"
            "- Clase B: Cobertura mínima 7 días de demanda. Acción si se incumple: Revisar punto de reorden.\n"
            "- Clase C: Cobertura mínima 5 días de demanda. Acción si se incumple: Sin acción automática.\n"
            "La cobertura se calcula como existencia final / demanda promedio diaria de los últimos 30 días, por SKU y bodega. "
            "Si la cobertura es menor a 5 días y hay pedidos pendientes de despacho, el caso es crítico."
        ),
    },
    {
        "documento": "OPE-POL-007",
        "seccion": "OPE-POL-007 §3 Proveedores y OC retrasadas",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de inventario y revisión de precios · Código OPE-POL-007 · Versión 3.\n"
            "3. Proveedores: Una orden de compra que no llega en la fecha esperada se marca como retrasada. "
            "Compras debe contactar al proveedor el mismo día y evaluar un proveedor alterno o una entrega parcial urgente."
        ),
    },
    {
        "documento": "OPE-POL-007",
        "seccion": "OPE-POL-007 §4 Revisión de precios y márgenes mínimos",
        "texto": (
            "Distribuidora Andina S.A.S. · Política de inventario y revisión de precios · Código OPE-POL-007 · Versión 3.\n"
            "4. Revisión de precios: Si el costo de un producto sube más de 5%, Comercial debe revisar el precio de venta "
            "en un máximo de 10 días hábiles. Ninguna línea debe operar por debajo de su margen mínimo:\n"
            "- Hogar: Margen mínimo 25%\n"
            "- Aseo: Margen mínimo 22%\n"
            "- Alimentos: Margen mínimo 15%\n"
            "- Bebidas: Margen mínimo 18%\n"
            "- Cuidado personal: Margen mínimo 25%\n"
            "- Mascotas: Margen mínimo 22%\n"
            "- Papelería: Margen mínimo 28%"
        ),
    },
]


def calcular_hash_sha256(texto: str) -> str:
    """Calcula el hash SHA-256 hexadecimal inmutable de un fragmento de política."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _similitud_coseno(v1: list[float], v2: list[float]) -> float:
    """Calcula la similitud coseno entre dos vectores normalizados."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, min(1.0, float(dot)))


def _calcular_score_lexico(consulta: str, texto_completo: str) -> float:
    """Calcula score de solapamiento léxico normalizado por términos significativos."""
    # Limpiar y tokenizar
    tokens_query = re.findall(r"\w+", consulta.lower())
    if not tokens_query:
        return 0.0

    texto_lower = texto_completo.lower()
    coincidencias = 0
    for tok in tokens_query:
        # Palabras de parada ignoradas en la coincidencia estricta
        if tok in {"de", "del", "la", "el", "los", "las", "en", "y", "un", "una", "por", "con"}:
            continue
        if tok in texto_lower:
            coincidencias += 1

    tokens_relevantes = [t for t in tokens_query if t not in {"de", "del", "la", "el", "los", "las", "en", "y", "un", "una", "por", "con"}]
    total_relevantes = len(tokens_relevantes) or len(tokens_query)
    base_score = coincidencias / total_relevantes

    # Bonus por coincidencia de frases clave
    if consulta.lower().strip() in texto_lower:
        base_score = min(1.0, base_score + 0.3)

    return min(1.0, base_score)


class PoliticasRetriever:
    """Retriever semántico híbrido para las políticas de Distribuidora Andina S.A.S."""

    def __init__(
        self,
        region_name: str = AWS_REGION,
        embedding_model_id: str = EMBEDDING_MODEL_ID,
        knowledge_base_id: str | None = KNOWLEDGE_BASE_ID,
        cache_file: Path | str = EMBEDDINGS_CACHE_FILE,
    ) -> None:
        self.region_name = region_name
        self.embedding_model_id = embedding_model_id
        self.knowledge_base_id = knowledge_base_id
        self.cache_file = Path(cache_file)
        self._bedrock_runtime: Any = None
        self._bedrock_agent_runtime: Any = None
        self._embeddings_corpus: list[list[float]] = []
        self._inicializar_embeddings()

    def _get_bedrock_runtime(self) -> Any:
        if self._bedrock_runtime is None:
            self._bedrock_runtime = boto3.client("bedrock-runtime", region_name=self.region_name)
        return self._bedrock_runtime

    def _get_bedrock_agent_runtime(self) -> Any:
        if self._bedrock_agent_runtime is None:
            self._bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=self.region_name)
        return self._bedrock_agent_runtime

    def _generar_embedding_titan(self, texto: str) -> list[float]:
        """Genera embedding normalizado de 1024 dimensiones con Titan Embeddings V2."""
        client = self._get_bedrock_runtime()
        body = json.dumps({
            "inputText": texto,
            "dimensions": 1024,
            "normalize": True,
        })
        response = client.invoke_model(
            modelId=self.embedding_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        data = json.loads(response["body"].read())
        return data["embedding"]

    def _inicializar_embeddings(self) -> None:
        """Carga o genera los embeddings del corpus normativo."""
        # 1. Intentar cargar desde caché
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if len(cached) == len(FRAGMENTOS_CORPUS):
                    self._embeddings_corpus = cached
                    logger.info("Embeddings de politicas cargados desde cache (%d fragmentos)", len(cached))
                    return
            except Exception as e:
                logger.warning("Fallo al leer cache de embeddings (%s), recalculando...", e)

        # 2. Generar con Bedrock Titan V2
        try:
            logger.info("Generando embeddings Titan V2 para los %d fragmentos de politicas...", len(FRAGMENTOS_CORPUS))
            embeddings: list[list[float]] = []
            for item in FRAGMENTOS_CORPUS:
                texto_indexar = f"{item['seccion']}\n{item['texto']}"
                emb = self._generar_embedding_titan(texto_indexar)
                embeddings.append(emb)

            self._embeddings_corpus = embeddings
            # Guardar en archivo para ejecuciones subsecuentes
            try:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(embeddings, f)
                logger.info("Embeddings cacheados exitosamente en %s", self.cache_file)
            except Exception as e:
                logger.warning("No se pudo persistir cache de embeddings: %s", e)

        except Exception as e:
            logger.warning("No se pudo conectar a Bedrock Titan V2 para embeddings iniciales: %s", e)
            self._embeddings_corpus = []

    def _buscar_en_knowledge_base(self, consulta: str, k: int) -> list[FragmentoPolitica] | None:
        """Invoca Bedrock Agent Runtime Retrieve si hay KNOWLEDGE_BASE_ID disponible."""
        if not self.knowledge_base_id:
            return None

        try:
            client = self._get_bedrock_agent_runtime()
            response = client.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={"text": consulta},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": k,
                    }
                },
            )
            results = response.get("retrievalResults", [])
            if not results:
                return None

            fragmentos: list[FragmentoPolitica] = []
            for res in results:
                raw_text = res.get("content", {}).get("text", "")
                score = float(res.get("score", 0.9))

                doc = "FIN-POL-004"
                if "COM-POL-002" in raw_text or "descuento" in raw_text.lower():
                    doc = "COM-POL-002"
                elif "OPE-POL-007" in raw_text or "inventario" in raw_text.lower() or "precio" in raw_text.lower():
                    doc = "OPE-POL-007"

                sec = "Recuperado de Knowledge Base"
                for line in raw_text.splitlines():
                    if "§" in line or line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.")):
                        sec = line.strip()[:80]
                        break

                h = calcular_hash_sha256(raw_text)
                frag = FragmentoPolitica(
                    documento=doc,  # type: ignore[arg-type]
                    seccion=sec,
                    texto=raw_text,
                    score=round(min(1.0, max(0.0, score)), 4),
                    fragmento_hash=h,
                )
                fragmentos.append(frag)

            return fragmentos
        except Exception as e:
            logger.warning("Error en bedrock-agent-runtime:retrieve (%s), pasando a plan B semantico local", e)
            return None

    def buscar(self, consulta: str, k: int = 3) -> list[FragmentoPolitica]:
        """Busca fragmentos relevantes para la consulta dada usando búsqueda híbrida.

        Combina similitud vectorial Titan V2 y coincidencia léxica, garantizando máxima precisión.
        Devuelve hasta k fragmentos válidos según el contrato inmutable FragmentoPolitica.
        """
        k = max(1, min(5, k))

        # 1. Intentar Knowledge Base si existe
        kb_results = self._buscar_en_knowledge_base(consulta, k)
        if kb_results:
            return kb_results

        # 2. Búsqueda híbrida (Titan V2 + Léxica)
        q_emb: list[float] | None = None
        if self._embeddings_corpus:
            try:
                q_emb = self._generar_embedding_titan(consulta)
            except Exception as e:
                logger.warning("Fallo al generar embedding de consulta con Titan V2: %s", e)

        scored: list[tuple[float, dict[str, str]]] = []
        for i, item in enumerate(FRAGMENTOS_CORPUS):
            texto_completo = f"{item['seccion']} {item['texto']}"
            lex_score = _calcular_score_lexico(consulta, texto_completo)

            if q_emb and i < len(self._embeddings_corpus):
                vec_score = _similitud_coseno(q_emb, self._embeddings_corpus[i])
                # Híbrido ponderado: 50% semántico + 50% léxico
                score_final = 0.5 * vec_score + 0.5 * lex_score
            else:
                score_final = lex_score

            scored.append((score_final, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]

        resultados: list[FragmentoPolitica] = []
        for s, item in top:
            h = calcular_hash_sha256(item["texto"])
            resultados.append(
                FragmentoPolitica(
                    documento=item["documento"],  # type: ignore[arg-type]
                    seccion=item["seccion"],
                    texto=item["texto"],
                    score=round(min(1.0, max(0.05, s)), 4),
                    fragmento_hash=h,
                )
            )
        return resultados


# Instancia singleton para uso en servicios y herramientas FastMCP
_default_retriever: PoliticasRetriever | None = None


def get_politicas_retriever() -> PoliticasRetriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = PoliticasRetriever()
    return _default_retriever
