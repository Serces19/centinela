"""backend/tools/politicas.py

Herramienta FastMCP `buscar_politica` para la recuperación normativa segura en Centinela.

Flujo:
1. Recibe BuscarPoliticaIn (consulta y k).
2. Recupera fragmentos de políticas mediante PoliticasRetriever.
3. Evalúa cada fragmento recuperado con aplicar_guardrail para detectar inyecciones de prompt
   (escenario EJ-03: política envenenada con instrucciones maliciosas).
4. Si algún fragmento presenta un intento de manipulación o ataque, marca guardrail_ataque_detectado = True.
5. Garantiza la integridad inmutable de cada fragmento sellándolo con su hash SHA-256.
6. Retorna BuscarPoliticaOut.
"""

from __future__ import annotations

import hashlib
import logging
from fastmcp import FastMCP

from contracts.herramientas import BuscarPoliticaIn, BuscarPoliticaOut, FragmentoPolitica
from services.guardrail import aplicar_guardrail
from services.knowledge import PoliticasRetriever, get_politicas_retriever

logger = logging.getLogger(__name__)

mcp = FastMCP("centinela-politicas")


def buscar_politica(
    params: BuscarPoliticaIn,
    retriever: PoliticasRetriever | None = None,
) -> BuscarPoliticaOut:
    """Ejecuta la búsqueda semántica de políticas corporativas con análisis de seguridad.

    Args:
        params: BuscarPoliticaIn con la consulta y el número de resultados k.
        retriever: PoliticasRetriever opcional (usa el singleton por defecto).

    Returns:
        BuscarPoliticaOut con la lista de fragmentos y el estado de detección del guardrail.
    """
    retriever_inst = retriever or get_politicas_retriever()
    fragmentos_raw = retriever_inst.buscar(consulta=params.consulta, k=params.k)

    ataque_detectado = False
    fragmentos_procesados: list[FragmentoPolitica] = []

    for frag in fragmentos_raw:
        # Analizar el texto del fragmento con el Guardrail (defensa contra EJ-03)
        res_guardrail = aplicar_guardrail(texto=frag.texto, fuente="INPUT")
        if res_guardrail.ataque_detectado:
            ataque_detectado = True
            logger.warning(
                "Ataque o inyección de prompt detectada en fragmento normativo (%s - %s)",
                frag.documento,
                frag.seccion,
            )

        # Usar el texto procesado (anonimizado si contenía PII) y calcular hash
        texto_final = res_guardrail.texto
        f_hash = hashlib.sha256(texto_final.encode("utf-8")).hexdigest()

        frag_limpio = FragmentoPolitica(
            documento=frag.documento,
            seccion=frag.seccion,
            texto=texto_final,
            score=frag.score,
            fragmento_hash=f_hash,
        )
        fragmentos_procesados.append(frag_limpio)

    return BuscarPoliticaOut(
        fragmentos=fragmentos_procesados,
        guardrail_ataque_detectado=ataque_detectado,
    )


@mcp.tool(name="buscar_politica")
def mcp_buscar_politica(params: BuscarPoliticaIn) -> BuscarPoliticaOut:
    """Busca fragmentos normativos en las políticas corporativas (COM-POL-002, FIN-POL-004, OPE-POL-007)."""
    return buscar_politica(params)


# Alias explícito para interoperabilidad con agentes
ejecutar_buscar_politica = buscar_politica
