# evals/test_escenarios_e2e.py
"""Pruebas E2E de ciclo de vida completo para los escenarios clave de Centinela:

1. Escenario 1 (PR08 - Alza de Costos en Hogar):
   - Detección determinista por Vigía a corte 2026-08-15.
   - Formulación de propuesta de ajuste de precios con impacto calculado ~$23.55M COP.
   - Aprobación humana y generación de borradores sandbox://.
   - Sello y verificación criptográfica de la bitácora.

2. Escenario 2 (C0496 - Mora y Cupo Excedido):
   - Detección a corte 2026-09-30 con $48.647.744 COP en riesgo.
   - Propuesta de gestión de cartera (ContactoCartera).
   - Edición humana de parámetros (elevación a 'bloqueo_despachos').
   - Verificación de borrador editado y bitácora válida.

3. Escenario 4 (V03 - Descuentos Fuera de Política):
   - Detección a corte 2026-09-30 con $8.096.844 COP en riesgo.
   - Propuesta de revisión de descuentos (RevisionDescuentos).
   - Rechazo humano motivado (>= 10 caracteres).
   - Transición a RECHAZADA, persistencia en config/feedback y bitácora íntegra.
"""

from datetime import date
import pytest

from agents.estratega import generar_propuesta
from agents.pipeline import aplicar_decision_humana
from agents.vigia import generar_alertas
from contracts.agentes import (
    AjustePrecio,
    ContactoCartera,
    DiagnosticoLLM,
    Propuesta,
    RevisionDescuentos,
)
from contracts.alertas import Alerta
from contracts.base import EstadoAlerta, Severidad
from contracts.bitacora import Evento, verificar_cadena
from contracts.decision import DecisionRequest
from contracts.evidencia import CifraTrazable, CitaPolitica
from services.persistencia import persistencia_service


@pytest.fixture(autouse=True)
def setup_persistencia():
    """Asegura entorno de persistencia en memoria aislado para cada test."""
    persistencia_service.use_memory = True
    persistencia_service._mem_alertas.clear()
    persistencia_service._mem_bitacora.clear()
    persistencia_service._mem_trazas.clear()
    persistencia_service._mem_propuestas.clear()
    persistencia_service._mem_resultados.clear()
    persistencia_service._mem_feedback.clear()


@pytest.mark.asyncio
async def test_escenario_s1_ciclo_completo_aprobacion():
    """Ciclo de vida completo S1: Vigía -> Analista/Estratega -> Aprobación -> Ejecución -> Bitácora."""
    corte = date(2026, 8, 15)
    alertas = generar_alertas(corte)
    persistencia_service.persistir_alertas_vigia(alertas)

    # 1. Vigía detecta S1 (costo|PR08)
    alerta_s1 = next((a for a in alertas if a.huella_causa == "costo|PR08"), None)
    assert alerta_s1 is not None, "Alerta S1 (costo|PR08) debe ser detectada a corte 2026-08-15"
    assert alerta_s1.severidad in (Severidad.ALTA, Severidad.CRITICA)
    assert abs(alerta_s1.dinero_en_riesgo_cop - 23558346) / 23558346 < 0.01

    # 2. Diagnóstico y Estratega
    diagnostico = DiagnosticoLLM(
        resumen="Incremento de costo del proveedor PR08 en cuatro SKU de la linea Hogar",
        causa_raiz="Aumento unilateral superior al umbral del cinco por ciento sin previo aviso segun OPE-POL-007",
        cifras=[
            CifraTrazable(etiqueta="Dinero en riesgo", valor=23522184.0, unidad="COP", consulta_id="Q-0123456789ab"),
        ],
        politicas=[
            CitaPolitica(
                documento="OPE-POL-007",
                seccion="§4 Notificación de cambios de costo",
                fragmento_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            )
        ],
        supuestos=["Volumen de ventas mensual estable"],
        evidencia_suficiente=True,
        confianza=0.9,
    )
    propuesta, _ = await generar_propuesta(alerta_s1, diagnostico)
    assert len(propuesta.acciones) >= 1
    accion = propuesta.acciones[0]
    assert isinstance(accion.parametros, AjustePrecio)
    assert accion.impacto.valor_cop > 0

    # Avanzar a PROPUESTA (NUEVA -> EN_ANALISIS -> PROPUESTA)
    alerta_an = alerta_s1.avanzar(EstadoAlerta.EN_ANALISIS)
    persistencia_service.actualizar_alerta(alerta_an)
    alerta_prop = alerta_an.avanzar(EstadoAlerta.PROPUESTA)
    persistencia_service.actualizar_alerta(alerta_prop)
    persistencia_service.sellar_evento(
        alerta_id=alerta_s1.alerta_id,
        evento=Evento.PROPUESTA_GENERADA,
        actor="estratega",
        payload={"num_acciones": len(propuesta.acciones)},
    )

    # 3. Decisión Humana: APROBAR
    decision_req = DecisionRequest(
        decision="aprobar",
        accion_ids=[accion.accion_id],
        decidido_por="usuario:sergio.arquitecto",
    )
    alerta_final, resultado = aplicar_decision_humana(
        alerta_id=alerta_s1.alerta_id,
        decision=decision_req,
        version_previa=alerta_prop.version,
    )

    # 4. Validar estado EJECUTADA y borradores sandbox
    assert alerta_final.estado == EstadoAlerta.EJECUTADA
    assert resultado.ok is True
    assert len(resultado.borradores) == 1
    assert resultado.borradores[0].destino.startswith(f"sandbox://ejecucion/{alerta_s1.alerta_id}")

    # 5. Validar Bitácora Criptográfica
    bitacora = persistencia_service.obtener_bitacora(alerta_s1.alerta_id)
    assert len(bitacora) >= 4
    assert verificar_cadena(bitacora) is True


@pytest.mark.asyncio
async def test_escenario_s2_ciclo_completo_edicion():
    """Ciclo de vida completo S2: Vigía -> Estratega -> Edición de Parámetros -> Ejecución -> Bitácora."""
    corte = date(2026, 9, 30)
    alertas = generar_alertas(corte)
    persistencia_service.persistir_alertas_vigia(alertas)

    # 1. Vigía detecta S2 (saldo_vencido|C0496)
    alerta_s2 = next((a for a in alertas if a.huella_causa == "saldo_vencido|C0496"), None)
    assert alerta_s2 is not None, "Alerta S2 debe ser detectada a corte 2026-09-30"
    assert alerta_s2.dinero_en_riesgo_cop == 48647744

    # 2. Propuesta de Estratega
    diagnostico = DiagnosticoLLM(
        resumen="Mora grave y cupo de credito excedido para cliente C0496",
        causa_raiz="Incumplimiento de politicas de credito FIN-POL-004 con saldo vencido superior a sesenta dias",
        cifras=[
            CifraTrazable(etiqueta="Saldo vencido", valor=48647744.0, unidad="COP", consulta_id="Q-0123456789cd"),
        ],
        politicas=[
            CitaPolitica(
                documento="FIN-POL-004",
                seccion="§4 Gestión de cobro y suspensión de despachos",
                fragmento_hash="abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            )
        ],
        evidencia_suficiente=True,
        confianza=0.95,
    )
    propuesta, _ = await generar_propuesta(alerta_s2, diagnostico)
    assert len(propuesta.acciones) >= 1
    accion = propuesta.acciones[0]
    assert isinstance(accion.parametros, ContactoCartera)

    alerta_an = alerta_s2.avanzar(EstadoAlerta.EN_ANALISIS)
    persistencia_service.actualizar_alerta(alerta_an)
    alerta_prop = alerta_an.avanzar(EstadoAlerta.PROPUESTA)
    persistencia_service.actualizar_alerta(alerta_prop)
    persistencia_service.sellar_evento(
        alerta_id=alerta_s2.alerta_id,
        evento=Evento.PROPUESTA_GENERADA,
        actor="estratega",
        payload={"num_acciones": len(propuesta.acciones)},
    )

    # 3. Decisión Humana: EDITAR (elevar nivel a 'bloqueo_despachos')
    nueva_accion_param = ContactoCartera(cliente_id="C0496", nivel="bloqueo_despachos")
    decision_req = DecisionRequest(
        decision="editar",
        accion_ids=[accion.accion_id],
        ediciones={accion.accion_id: nueva_accion_param},
        decidido_por="usuario:jefe.credito",
    )

    alerta_final, resultado = aplicar_decision_humana(
        alerta_id=alerta_s2.alerta_id,
        decision=decision_req,
        version_previa=alerta_prop.version,
    )

    # 4. Validar estado EJECUTADA y que el borrador refleje la edición
    assert alerta_final.estado == EstadoAlerta.EJECUTADA
    assert resultado.ok is True
    assert len(resultado.borradores) == 1
    borrador = resultado.borradores[0]
    assert "bloqueo_despachos" in borrador.contenido

    # 5. Validar Bitácora Criptográfica
    bitacora = persistencia_service.obtener_bitacora(alerta_s2.alerta_id)
    assert len(bitacora) >= 4
    assert verificar_cadena(bitacora) is True


@pytest.mark.asyncio
async def test_escenario_s4_ciclo_completo_rechazo():
    """Ciclo de vida completo S4: Vigía -> Estratega -> Rechazo con Motivo Obligatorio -> Feedback -> Bitácora."""
    corte = date(2026, 9, 30)
    alertas = generar_alertas(corte)
    persistencia_service.persistir_alertas_vigia(alertas)

    # 1. Vigía detecta S4 (descuento_en_exceso|V03)
    alerta_s4 = next((a for a in alertas if a.huella_causa == "descuento_en_exceso|V03"), None)
    assert alerta_s4 is not None, "Alerta S4 debe ser detectada a corte 2026-09-30"
    assert abs(alerta_s4.dinero_en_riesgo_cop - 8096844) <= 1

    # 2. Diagnóstico y Estratega
    diagnostico = DiagnosticoLLM(
        resumen="Descuentos comerciales por fuera de los topes de COM-POL-002 otorgados por vendedor V03",
        causa_raiz="Aplicacion reiterada de descuentos superiores al limite comercial autorizado sin aprobacion de gerencia",
        cifras=[
            CifraTrazable(etiqueta="Exceso de descuento", valor=8096844.0, unidad="COP", consulta_id="Q-0123456789ef"),
        ],
        politicas=[
            CitaPolitica(
                documento="COM-POL-002",
                seccion="§2 Topes máximos de descuento",
                fragmento_hash="1122334455667788990011223344556677889900112233445566778899001122",
            )
        ],
        evidencia_suficiente=True,
        confianza=0.9,
    )
    propuesta, _ = await generar_propuesta(alerta_s4, diagnostico)
    assert len(propuesta.acciones) >= 1
    accion = propuesta.acciones[0]
    assert isinstance(accion.parametros, RevisionDescuentos)

    alerta_an = alerta_s4.avanzar(EstadoAlerta.EN_ANALISIS)
    persistencia_service.actualizar_alerta(alerta_an)
    alerta_prop = alerta_an.avanzar(EstadoAlerta.PROPUESTA)
    persistencia_service.actualizar_alerta(alerta_prop)
    persistencia_service.sellar_evento(
        alerta_id=alerta_s4.alerta_id,
        evento=Evento.PROPUESTA_GENERADA,
        actor="estratega",
        payload={"num_acciones": len(propuesta.acciones)},
    )

    # 3. Decisión Humana: RECHAZAR con motivo válido (> 10 caracteres)
    motivo_rechazo = "Descuentos autorizados excepcionalmente por Gerencia General para cierre de campana semestral."
    decision_req = DecisionRequest(
        decision="rechazar",
        accion_ids=[],
        motivo=motivo_rechazo,
        decidido_por="usuario:gerente.comercial",
    )

    alerta_final, resultado = aplicar_decision_humana(
        alerta_id=alerta_s4.alerta_id,
        decision=decision_req,
        version_previa=alerta_prop.version,
    )

    # 4. Validar estado RECHAZADA y ausencia de borradores
    assert alerta_final.estado == EstadoAlerta.RECHAZADA
    assert resultado.ok is True
    assert len(resultado.borradores) == 0
    assert "Rechazada" in (resultado.error or "")

    # 5. Validar que el feedback fue archivado para aprendizaje por rechazo
    feedbacks = persistencia_service.obtener_feedback(alerta_s4.alerta_id)
    assert len(feedbacks) >= 1
    assert feedbacks[0]["motivo"] == motivo_rechazo
    assert feedbacks[0]["actor"] == "usuario:gerente.comercial"

    # 6. Validar Bitácora Criptográfica
    bitacora = persistencia_service.obtener_bitacora(alerta_s4.alerta_id)
    assert len(bitacora) >= 3
    assert verificar_cadena(bitacora) is True
    evento_dec = next((e for e in bitacora if e.evento == Evento.DECISION_HUMANA), None)
    assert evento_dec is not None
    assert evento_dec.payload["decision"] == "rechazar"
    assert evento_dec.payload["motivo"] == motivo_rechazo
