# backend/agents/pipeline.py
"""Pipeline de agentes de Centinela: máquina de estados explícita y persistida.

Estados (contracts.base.EstadoAlerta):
    nueva -> en_analisis -> propuesta -> aprobada -> ejecutada
                         |            -> rechazada
                         -> sin_evidencia

La pausa de aprobación humana es el estado persistido `propuesta`: el flujo termina ahí,
no consume cómputo mientras espera, y se reanuda con `aplicar_decision_humana`.
"""

from datetime import date
import logging
import uuid

from agents.analista import analizar_alerta
from agents.estratega import generar_propuesta
from contracts.agentes import Propuesta
from contracts.alertas import Alerta
from contracts.base import EstadoAlerta
from contracts.bitacora import Evento
from contracts.decision import Borrador, DecisionRequest, ResultadoEjecucion
from services.persistencia import persistencia_service
from services.umbrales import cargar_autonomia

logger = logging.getLogger("centinela.agente.pipeline")


async def procesar_alerta_completa(
    alerta_id: str,
    corte: date,
    run_id: str | None = None,
) -> tuple[Alerta, Propuesta | None]:
    """Lleva una alerta de `nueva` a `propuesta` (o `sin_evidencia`). Idempotente.

    Si la alerta ya tiene propuesta o ya fue decidida, devuelve el estado guardado sin
    volver a invocar al modelo.
    """
    alerta = persistencia_service.obtener_alerta(alerta_id)
    if not alerta:
        raise ValueError(f"Alerta con ID '{alerta_id}' no encontrada.")

    if alerta.estado not in (EstadoAlerta.NUEVA, EstadoAlerta.EN_ANALISIS):
        return alerta, persistencia_service.obtener_propuesta(alerta_id)

    if alerta.estado == EstadoAlerta.NUEVA:
        alerta = alerta.avanzar(EstadoAlerta.EN_ANALISIS)
    alerta = alerta.model_copy(update={"paso_actual": "analista"})
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
            "num_cifras": len(diagnostico.cifras),
            "num_politicas": len(diagnostico.politicas),
        },
    )

    if not diagnostico.evidencia_suficiente:
        alerta = alerta.avanzar(EstadoAlerta.SIN_EVIDENCIA).model_copy(update={"paso_actual": "ninguno"})
        persistencia_service.actualizar_alerta(alerta)
        return alerta, None

    alerta = alerta.model_copy(update={"paso_actual": "estratega"})
    persistencia_service.actualizar_alerta(alerta)
    propuesta, _ = await generar_propuesta(alerta, diagnostico)
    alerta = alerta.avanzar(EstadoAlerta.PROPUESTA).model_copy(update={"paso_actual": "ninguno"})
    persistencia_service.actualizar_alerta(alerta)

    persistencia_service.sellar_evento(
        alerta_id=alerta.alerta_id,
        evento=Evento.PROPUESTA_GENERADA,
        actor="estratega",
        payload={
            "num_acciones": len(propuesta.acciones),
            "modelo": propuesta.modelo,
            "acciones_resumen": [
                {"titulo": a.titulo, "impacto_cop": a.impacto.valor_cop} for a in propuesta.acciones
            ],
        },
    )
    return alerta, propuesta


def _generar_borradores(
    alerta_id: str,
    propuesta: Propuesta | None,
    decision: DecisionRequest,
) -> list[Borrador]:
    """Un borrador `sandbox://` por cada acción aprobada o editada. Nunca hay efecto externo."""
    acciones = {a.accion_id: a for a in propuesta.acciones} if propuesta else {}
    autonomia = cargar_autonomia()
    borradores: list[Borrador] = []
    for acc_id in decision.accion_ids:
        acc = acciones.get(acc_id)
        if acc and autonomia.get((decision.ediciones.get(acc_id) or acc.parametros).tipo) == "informa":
            continue   # nivel "informa": se avisa, no se prepara ninguna acción
        tipo = "tarea"
        contenido = f"Ejecución autorizada para la acción {acc_id}."
        if acc:
            p = decision.ediciones.get(acc_id) or acc.parametros
            if p.tipo == "contacto_cartera":
                tipo = "correo"
                contenido = f"Borrador de gestión de cartera para {p.cliente_id} (nivel: {p.nivel})."
            elif p.tipo == "expeditar_oc":
                tipo = "orden_compra"
                contenido = f"Borrador de expedición de la OC {p.oc_id} a {p.proveedor_id} en {p.bodega_id}."
            elif p.tipo == "reactivar_cliente":
                tipo = "correo"
                contenido = f"Borrador de reactivación del cliente {p.cliente_id} por {p.canal}."
            elif p.tipo == "ajuste_precio":
                contenido = f"Borrador de actualización de precios para {', '.join(p.skus)} (+{p.pct_ajuste} %)."
            elif p.tipo == "revision_descuentos":
                contenido = f"Borrador de directriz de cotización para el vendedor {p.vendedor_id} ({p.medida})."
            elif p.tipo == "corregir_venta_bajo_costo":
                contenido = f"Borrador de ajuste de precio mínimo para {', '.join(p.skus)}."
        borradores.append(
            Borrador(
                artefacto_id=f"ART-{uuid.uuid4().hex[:8]}",
                accion_id=acc_id,
                tipo=tipo,
                destino=f"sandbox://ejecucion/{alerta_id}/{acc_id}",
                contenido=contenido,
                estado="borrador",
            )
        )
    return borradores


def aplicar_decision_humana(
    alerta_id: str,
    decision: DecisionRequest,
    version_previa: int | None = None,
) -> tuple[Alerta, ResultadoEjecucion]:
    """Aplica la decisión humana (aprobar, editar, rechazar). Idempotente por estado."""
    alerta = persistencia_service.obtener_alerta(alerta_id)
    if not alerta:
        raise ValueError(f"Alerta '{alerta_id}' no encontrada.")

    if version_previa is not None and alerta.version != version_previa:
        raise ValueError(f"Conflicto de versión optimista: actual={alerta.version}, esperada={version_previa}")

    if alerta.estado != EstadoAlerta.PROPUESTA:
        if alerta.estado in (EstadoAlerta.APROBADA, EstadoAlerta.EJECUTADA, EstadoAlerta.RECHAZADA):
            previo = persistencia_service.obtener_resultado_ejecucion(alerta_id)
            if previo:
                return alerta, previo
        raise ValueError(
            f"Transición inválida desde estado '{alerta.estado.value}'. Solo se permite desde 'propuesta'."
        )

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

    if decision.decision in ("aprobar", "editar"):
        aprobada = alerta.avanzar(EstadoAlerta.APROBADA)
        persistencia_service.actualizar_alerta(aprobada, version_previa=alerta.version)

        borradores = _generar_borradores(alerta_id, propuesta, decision)

        ejecutada = aprobada.avanzar(EstadoAlerta.EJECUTADA)
        persistencia_service.actualizar_alerta(ejecutada, version_previa=aprobada.version)

        persistencia_service.sellar_evento(
            alerta_id=alerta_id,
            evento=Evento.ACCION_EJECUTADA,
            actor="ejecutor",
            payload={
                "borradores_creados": len(borradores),
                "artefactos": [b.artefacto_id for b in borradores],
                "ok": True,
            },
        )
        resultado = ResultadoEjecucion(alerta_id=alerta_id, borradores=borradores, ok=True)
        persistencia_service.guardar_resultado_ejecucion(resultado)
        return ejecutada, resultado

    rechazada = alerta.avanzar(EstadoAlerta.RECHAZADA)
    persistencia_service.actualizar_alerta(rechazada, version_previa=alerta.version)
    persistencia_service.guardar_feedback(
        alerta_id=alerta_id,
        motivo=decision.motivo or "",
        actor=decision.decidido_por,
        huella_causa=alerta.huella_causa,
        tipos_accion=sorted({a.parametros.tipo for a in propuesta.acciones}) if propuesta else [],
    )
    resultado = ResultadoEjecucion(
        alerta_id=alerta_id,
        borradores=[],
        ok=True,
        error=f"Rechazada: {decision.motivo}",
    )
    persistencia_service.guardar_resultado_ejecucion(resultado)
    return rechazada, resultado
