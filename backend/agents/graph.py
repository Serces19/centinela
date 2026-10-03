# backend/agents/graph.py
"""Orquestador LangGraph con Human-in-the-Loop para Centinela (Fase 2D).

Grafo de ejecución StateGraph(EstadoGrafo):
1. nodo_vigia: Genera y persiste alertas deterministas para el corte simulado.
2. nodo_analista: Investiga la alerta activa mediante Claude Haiku 4.5 y herramientas.
3. nodo_estratega: Formula propuesta con cálculo determinista de impacto económico.
4. nodo_aprobacion_humana: Pausa la ejecución con interrupt(InterruptPayload) en EstadoAlerta.PROPUESTA.
5. nodo_ejecutor: Reanuda tras DecisionRequest humana (Command(resume=...)), genera borradores sandbox y sella bitácora.

Checkpointer:
- DynamoDBSaver sobre la tabla `centinela_checkpoints` (thread_id = alerta_id).
- Fallback automático a MemorySaver para pruebas locales y fallback rápido.
"""

from datetime import date, datetime, timezone
import json
import logging
import os
import uuid
from typing import Any, Sequence

import boto3
from botocore.exceptions import ClientError
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agents.analista import analizar_alerta
from agents.estratega import generar_propuesta
from agents.vigia import generar_alertas
from contracts.agentes import DiagnosticoLLM, Propuesta
from contracts.alertas import Alerta, Hallazgo
from contracts.base import AlertaId, EstadoAlerta, transicion_valida
from contracts.bitacora import EntradaBitacora, Evento
from contracts.decision import Borrador, DecisionRequest, ResultadoEjecucion
from contracts.herramientas import EstadoGrafo, InterruptPayload
from services.persistencia import persistencia_service

logger = logging.getLogger("centinela.agente.grafo")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


# -----------------------------------------------------------------------------
# Checkpointer DynamoDB con Fallback en Memoria
# -----------------------------------------------------------------------------
class DynamoDBSaver(MemorySaver):
    """Checkpointer para LangGraph respaldado por DynamoDB (tabla centinela_checkpoints).

    Usa almacenamiento en memoria para ejecución de baja latencia y sincroniza
    puntos de control en DynamoDB con clave primaria thread_id y rango checkpoint_id.
    """

    def __init__(self, table_name: str = "centinela_checkpoints", region_name: str | None = None):
        super().__init__()
        self.table_name = table_name
        self.region_name = region_name or AWS_REGION
        self._dynamodb_disponible = False
        self._table = None

        if os.environ.get("CENTINELA_PERSISTENCIA_BACKEND", "dynamodb").lower() != "memory":
            try:
                dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
                self._table = dynamodb.Table(self.table_name)
                self._dynamodb_disponible = True
            except Exception as e:
                logger.info(f"DynamoDBSaver operando con fallback en memoria ({e})")
                self._dynamodb_disponible = False

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        res_config = super().put(config, checkpoint, metadata, new_versions)
        if self._dynamodb_disponible:
            try:
                thread_id = config["configurable"]["thread_id"]
                checkpoint_id = checkpoint["id"]
                item = {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "checkpoint_data": json.dumps(checkpoint, default=str),
                    "metadata": json.dumps(metadata, default=str),
                }
                if self._table is not None:
                    self._table.put_item(Item=item)
            except Exception as e:
                logger.warning(f"Error sincronizando checkpoint en DynamoDB: {e}")
        return res_config


# -----------------------------------------------------------------------------
# Nodos del Grafo
# -----------------------------------------------------------------------------
def nodo_vigia(state: EstadoGrafo) -> dict[str, Any]:
    """Genera hallazgos y alertas deterministas con el corte temporal simulado."""
    logger.info(f"[Vigia] Evaluando corte simulado {state.corte}")
    alertas = generar_alertas(state.corte)
    persistencia_service.persistir_alertas_vigia(alertas)

    alerta_seleccionada: Alerta | None = None
    if state.alerta_id:
        alerta_seleccionada = persistencia_service.obtener_alerta(state.alerta_id)
        if not alerta_seleccionada:
            for a in alertas:
                if a.alerta_id == state.alerta_id:
                    alerta_seleccionada = a
                    break

    if alerta_seleccionada is None and alertas:
        # Tomar la de mayor dinero en riesgo
        alerta_seleccionada = alertas[0]

    if alerta_seleccionada is None:
        logger.info("[Vigia] No se detectaron alertas abiertas.")
        return {"hallazgos": []}

    # Transición de estado: NUEVA -> EN_ANALISIS
    if alerta_seleccionada.estado == EstadoAlerta.NUEVA:
        alerta_act = alerta_seleccionada.avanzar(EstadoAlerta.EN_ANALISIS)
        persistencia_service.actualizar_alerta(alerta_act, version_previa=alerta_seleccionada.version)
        alerta_seleccionada = alerta_act

    return {
        "alerta_id": alerta_seleccionada.alerta_id,
        "hallazgos": alerta_seleccionada.hallazgos,
    }


async def nodo_analista(state: EstadoGrafo) -> dict[str, Any]:
    """Ejecuta el análisis investigativo con Claude Haiku 4.5."""
    if not state.alerta_id:
        return {}

    alerta = persistencia_service.obtener_alerta(state.alerta_id)
    if not alerta:
        raise ValueError(f"Alerta {state.alerta_id} no encontrada en persistencia")

    if state.diagnostico is not None:
        diagnostico = state.diagnostico
    else:
        logger.info(f"[Analista] Analizando alerta {alerta.alerta_id} ({alerta.huella_causa})")
        diagnostico, trazas = await analizar_alerta(alerta)

    # Sellar bitácora si no existe evento previo
    historial = persistencia_service.obtener_bitacora(alerta.alerta_id)
    if not any(e.evento == Evento.ANALISIS_COMPLETO for e in historial):
        persistencia_service.sellar_evento(
            alerta_id=alerta.alerta_id,
            evento=Evento.ANALISIS_COMPLETO,
            actor="analista",
            payload={
                "resumen": diagnostico.resumen,
                "evidencia_suficiente": diagnostico.evidencia_suficiente,
                "confianza": diagnostico.confianza,
                "num_cifras": len(diagnostico.cifras),
                "num_politicas": len(diagnostico.politicas),
            },
        )

    if not diagnostico.evidencia_suficiente:
        if transicion_valida(alerta.estado, EstadoAlerta.SIN_EVIDENCIA):
            alerta_act = alerta.avanzar(EstadoAlerta.SIN_EVIDENCIA)
            persistencia_service.actualizar_alerta(alerta_act, version_previa=alerta.version)

    return {"diagnostico": diagnostico}


async def nodo_estratega(state: EstadoGrafo) -> dict[str, Any]:
    """Genera la propuesta de remediación con cálculo de impacto económico."""
    if state.propuesta is not None:
        return {"propuesta": state.propuesta}

    if not state.alerta_id or not state.diagnostico:
        return {}

    alerta = persistencia_service.obtener_alerta(state.alerta_id)
    if not alerta:
        raise ValueError(f"Alerta {state.alerta_id} no encontrada")

    logger.info(f"[Estratega] Formulando propuesta para {alerta.alerta_id}")
    propuesta, trazas = await generar_propuesta(alerta, state.diagnostico)

    # Transición: EN_ANALISIS -> PROPUESTA
    if transicion_valida(alerta.estado, EstadoAlerta.PROPUESTA):
        alerta_act = alerta.avanzar(EstadoAlerta.PROPUESTA)
        persistencia_service.actualizar_alerta(alerta_act, version_previa=alerta.version)

    # Sellar bitácora
    persistencia_service.sellar_evento(
        alerta_id=alerta.alerta_id,
        evento=Evento.PROPUESTA_GENERADA,
        actor="estratega",
        payload={
            "num_acciones": len(propuesta.acciones),
            "modelo": propuesta.modelo,
            "acciones_resumen": [
                {"titulo": a.titulo, "impacto_cop": a.impacto.valor_cop}
                for a in propuesta.acciones
            ],
        },
    )

    return {"propuesta": propuesta}


def nodo_aprobacion_humana(state: EstadoGrafo) -> dict[str, Any]:
    """Punto de suspensión Human-in-the-Loop. Espera decisión humana."""
    logger.info(f"[HITL] Suspendiendo ejecución de alerta {state.alerta_id} a la espera de decisión humana.")

    # Generar interrupción con el payload tipado
    payload = InterruptPayload(alerta_id=state.alerta_id, propuesta=state.propuesta)
    decision_raw = interrupt(payload)

    # Al reanudar con Command(resume=...), procesamos la decisión
    if isinstance(decision_raw, DecisionRequest):
        decision_req = decision_raw
    elif isinstance(decision_raw, dict):
        decision_req = DecisionRequest.model_validate(decision_raw)
    else:
        raise ValueError(f"Formato de decisión inesperado: {type(decision_raw)}")

    # Sellar bitácora de decisión humana
    persistencia_service.sellar_evento(
        alerta_id=state.alerta_id,
        evento=Evento.DECISION_HUMANA,
        actor=decision_req.decidido_por,
        payload={
            "decision": decision_req.decision,
            "motivo": decision_req.motivo,
            "accion_ids": decision_req.accion_ids,
        },
    )

    return {"decision": decision_req}


def nodo_ejecutor(state: EstadoGrafo) -> dict[str, Any]:
    """Ejecuta la decisión humana aprobada o editada generando borradores en sandbox."""
    if not state.alerta_id or not state.decision:
        return {}

    alerta = persistencia_service.obtener_alerta(state.alerta_id)
    if not alerta:
        raise ValueError(f"Alerta {state.alerta_id} no encontrada")

    decision = state.decision
    borradores: list[Borrador] = []

    if decision.decision in ("aprobar", "editar"):
        # Transición: PROPUESTA -> APROBADA
        if transicion_valida(alerta.estado, EstadoAlerta.APROBADA):
            alerta_aprob = alerta.avanzar(EstadoAlerta.APROBADA)
            persistencia_service.actualizar_alerta(alerta_aprob, version_previa=alerta.version)
            alerta = alerta_aprob

        # Generar borradores sandbox para cada acción aprobada
        acciones_map = {}
        if state.propuesta:
            for a in state.propuesta.acciones:
                acciones_map[a.accion_id] = a

        for acc_id in decision.accion_ids:
            acc = acciones_map.get(acc_id)
            tipo_borrador = "tarea"
            contenido = f"Acción aprobada {acc_id} para alerta {alerta.alerta_id}."
            if acc:
                p = acc.parametros
                if p.tipo == "contacto_cartera":
                    tipo_borrador = "correo"
                    contenido = f"Borrador de notificación de cartera a cliente {p.cliente_id} (Nivel: {p.nivel})."
                elif p.tipo == "expeditar_oc":
                    tipo_borrador = "orden_compra"
                    contenido = f"Borrador de solicitud de expedición OC {p.oc_id} al proveedor {p.proveedor_id} en bodega {p.bodega_id}."
                elif p.tipo == "reactivar_cliente":
                    tipo_borrador = "correo"
                    contenido = f"Borrador de campaña de reactivación comercial para cliente {p.cliente_id} vía {p.canal}."
                elif p.tipo == "ajuste_precio":
                    tipo_borrador = "tarea"
                    contenido = f"Borrador de actualización de lista de precios para SKUs {p.skus} (+{p.pct_ajuste}%)."
                elif p.tipo == "revision_descuentos":
                    tipo_borrador = "tarea"
                    contenido = f"Borrador de directriz de cotizaciones para vendedor {p.vendedor_id} ({p.medida})."
                elif p.tipo == "corregir_venta_bajo_costo":
                    tipo_borrador = "tarea"
                    contenido = f"Borrador de bloqueo y ajuste de precio base para SKUs bajo costo: {p.skus}."

            borrador = Borrador(
                artefacto_id=f"ART-{uuid.uuid4().hex[:8]}",
                accion_id=acc_id,
                tipo=tipo_borrador,
                destino=f"sandbox://ejecucion/{alerta.alerta_id}/{acc_id}",
                contenido=contenido,
                estado="borrador",
            )
            borradores.append(borrador)

        # Transición: APROBADA -> EJECUTADA
        if transicion_valida(alerta.estado, EstadoAlerta.EJECUTADA):
            alerta_ejec = alerta.avanzar(EstadoAlerta.EJECUTADA)
            persistencia_service.actualizar_alerta(alerta_ejec, version_previa=alerta.version)
            alerta = alerta_ejec

        # Sellar bitácora de ejecución
        persistencia_service.sellar_evento(
            alerta_id=alerta.alerta_id,
            evento=Evento.ACCION_EJECUTADA,
            actor="ejecutor",
            payload={
                "borradores_creados": len(borradores),
                "artefactos": [b.artefacto_id for b in borradores],
                "ok": True,
            },
        )
        resultado = ResultadoEjecucion(alerta_id=alerta.alerta_id, borradores=borradores, ok=True)

    else:
        # Decisión: rechazar -> Transición: PROPUESTA -> RECHAZADA
        if transicion_valida(alerta.estado, EstadoAlerta.RECHAZADA):
            alerta_rech = alerta.avanzar(EstadoAlerta.RECHAZADA)
            persistencia_service.actualizar_alerta(alerta_rech, version_previa=alerta.version)
            alerta = alerta_rech

        resultado = ResultadoEjecucion(
            alerta_id=alerta.alerta_id,
            borradores=[],
            ok=True,
            error=f"Rechazada por usuario: {decision.motivo}",
        )

    persistencia_service.guardar_resultado_ejecucion(resultado)
    return {"resultado": resultado}


# -----------------------------------------------------------------------------
# Condiciones de Enrutamiento
# -----------------------------------------------------------------------------
def verificar_continuidad_vigia(state: EstadoGrafo) -> str:
    if state.alerta_id:
        return "analista"
    return END


def verificar_continuidad_analista(state: EstadoGrafo) -> str:
    if state.diagnostico and state.diagnostico.evidencia_suficiente:
        return "estratega"
    return END


# -----------------------------------------------------------------------------
# Construcción del Grafo
# -----------------------------------------------------------------------------
def construir_grafo(checkpointer: Any = None):
    """Compila el grafo StateGraph(EstadoGrafo) con checkpointer persistente."""
    saver = checkpointer if checkpointer is not None else DynamoDBSaver()

    workflow = StateGraph(EstadoGrafo)

    workflow.add_node("vigia", nodo_vigia)
    workflow.add_node("analista", nodo_analista)
    workflow.add_node("estratega", nodo_estratega)
    workflow.add_node("aprobacion_humana", nodo_aprobacion_humana)
    workflow.add_node("ejecutor", nodo_ejecutor)

    workflow.add_edge(START, "vigia")
    workflow.add_conditional_edges(
        "vigia",
        verificar_continuidad_vigia,
        {"analista": "analista", END: END},
    )
    workflow.add_conditional_edges(
        "analista",
        verificar_continuidad_analista,
        {"estratega": "estratega", END: END},
    )
    workflow.add_edge("estratega", "aprobacion_humana")
    workflow.add_edge("aprobacion_humana", "ejecutor")
    workflow.add_edge("ejecutor", END)

    return workflow.compile(checkpointer=saver)


# Singleton del grafo
grafo_centinela = construir_grafo()


# -----------------------------------------------------------------------------
# Funciones de Entrada de Pipeline
# -----------------------------------------------------------------------------
async def procesar_alerta_completa(
    alerta_id: str,
    corte: date,
    run_id: str | None = None,
    checkpointer: Any = None,
) -> tuple[Alerta, Propuesta | None]:
    """Procesa una alerta a través del flujo analista -> estratega hasta quedar en estado PROPUESTA."""
    r_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
    alerta = persistencia_service.obtener_alerta(alerta_id)
    if not alerta:
        raise ValueError(f"Alerta con ID '{alerta_id}' no encontrada.")

    # 1. Analista
    if alerta.estado == EstadoAlerta.NUEVA:
        alerta = alerta.avanzar(EstadoAlerta.EN_ANALISIS)
        persistencia_service.actualizar_alerta(alerta)

    diagnostico, _ = await analizar_alerta(alerta)

    persistencia_service.sellar_evento(
        alerta_id=alerta.alerta_id,
        evento=Evento.ANALISIS_COMPLETO,
        actor="analista",
        payload={
            "resumen": diagnostico.resumen,
            "evidencia_suficiente": diagnostico.evidencia_suficiente,
            "confianza": diagnostico.confianza,
        },
    )

    if not diagnostico.evidencia_suficiente:
        alerta = alerta.avanzar(EstadoAlerta.SIN_EVIDENCIA)
        persistencia_service.actualizar_alerta(alerta)
        return alerta, None

    # 2. Estratega
    propuesta, _ = await generar_propuesta(alerta, diagnostico)
    alerta = alerta.avanzar(EstadoAlerta.PROPUESTA)
    persistencia_service.actualizar_alerta(alerta)

    persistencia_service.sellar_evento(
        alerta_id=alerta.alerta_id,
        evento=Evento.PROPUESTA_GENERADA,
        actor="estratega",
        payload={
            "num_acciones": len(propuesta.acciones),
            "modelo": propuesta.modelo,
        },
    )

    return alerta, propuesta


def aplicar_decision_humana(
    alerta_id: str,
    decision: DecisionRequest,
    version_previa: int | None = None,
) -> tuple[Alerta, ResultadoEjecucion]:
    """Aplica la decisión humana de manera transaccional e idempotente (Gate Plan B y Resunción)."""
    alerta = persistencia_service.obtener_alerta(alerta_id)
    if not alerta:
        raise ValueError(f"Alerta '{alerta_id}' no encontrada.")

    if version_previa is not None and alerta.version != version_previa:
        raise ValueError(f"Conflicto de versión optimista: actual={alerta.version}, esperada={version_previa}")

    if alerta.estado != EstadoAlerta.PROPUESTA:
        # Verificar idempotencia: si ya fue ejecutada/rechazada y coincide
        if alerta.estado in (EstadoAlerta.APROBADA, EstadoAlerta.EJECUTADA, EstadoAlerta.RECHAZADA):
            res_prev = persistencia_service.obtener_resultado_ejecucion(alerta_id)
            if res_prev:
                return alerta, res_prev
        raise ValueError(f"Transición inválida desde estado '{alerta.estado.value}'. Solo se permite desde 'propuesta'.")

    # Sellar bitácora de decisión humana
    persistencia_service.sellar_evento(
        alerta_id=alerta_id,
        evento=Evento.DECISION_HUMANA,
        actor=decision.decidido_por,
        payload={
            "decision": decision.decision,
            "motivo": decision.motivo,
            "accion_ids": decision.accion_ids,
        },
    )

    propuesta = persistencia_service.obtener_propuesta(alerta_id)
    borradores: list[Borrador] = []

    if decision.decision in ("aprobar", "editar"):
        # PROPUESTA -> APROBADA
        alerta_aprob = alerta.avanzar(EstadoAlerta.APROBADA)
        persistencia_service.actualizar_alerta(alerta_aprob, version_previa=alerta.version)

        # Generar borradores
        acciones_map = {a.accion_id: a for a in propuesta.acciones} if propuesta else {}
        for acc_id in decision.accion_ids:
            acc = acciones_map.get(acc_id)
            tipo_b = "tarea"
            contenido = f"Ejecución autorizada para acción {acc_id}."
            if acc:
                p = acc.parametros
                if p.tipo == "contacto_cartera":
                    tipo_b = "correo"
                    contenido = f"Borrador de gestión de cartera para {p.cliente_id} ({p.nivel})."
                elif p.tipo == "expeditar_oc":
                    tipo_b = "orden_compra"
                    contenido = f"Borrador de expedición OC {p.oc_id} a {p.proveedor_id} en {p.bodega_id}."
                elif p.tipo == "reactivar_cliente":
                    tipo_b = "correo"
                    contenido = f"Borrador de reactivación para cliente {p.cliente_id} por {p.canal}."
                elif p.tipo == "ajuste_precio":
                    tipo_b = "tarea"
                    contenido = f"Borrador de actualización de precios para SKUs {p.skus} (+{p.pct_ajuste}%)."
                elif p.tipo == "revision_descuentos":
                    tipo_b = "tarea"
                    contenido = f"Borrador de directriz de cotización para vendedor {p.vendedor_id}."
                elif p.tipo == "corregir_venta_bajo_costo":
                    tipo_b = "tarea"
                    contenido = f"Borrador de ajuste de precio para venta bajo costo en SKUs {p.skus}."

            borradores.append(
                Borrador(
                    artefacto_id=f"ART-{uuid.uuid4().hex[:8]}",
                    accion_id=acc_id,
                    tipo=tipo_b,
                    destino=f"sandbox://ejecucion/{alerta_id}/{acc_id}",
                    contenido=contenido,
                    estado="borrador",
                )
            )

        # APROBADA -> EJECUTADA
        alerta_ejec = alerta_aprob.avanzar(EstadoAlerta.EJECUTADA)
        persistencia_service.actualizar_alerta(alerta_ejec, version_previa=alerta_aprob.version)

        # Sellar ejecución
        persistencia_service.sellar_evento(
            alerta_id=alerta_id,
            evento=Evento.ACCION_EJECUTADA,
            actor="ejecutor",
            payload={"borradores_generados": len(borradores), "ok": True},
        )
        resultado = ResultadoEjecucion(alerta_id=alerta_id, borradores=borradores, ok=True)
        persistencia_service.guardar_resultado_ejecucion(resultado)
        return alerta_ejec, resultado

    else:
        # Rechazada
        alerta_rech = alerta.avanzar(EstadoAlerta.RECHAZADA)
        persistencia_service.actualizar_alerta(alerta_rech, version_previa=alerta.version)
        resultado = ResultadoEjecucion(
            alerta_id=alerta_id,
            borradores=[],
            ok=True,
            error=f"Rechazada: {decision.motivo}",
        )
        persistencia_service.guardar_resultado_ejecucion(resultado)
        return alerta_rech, resultado
