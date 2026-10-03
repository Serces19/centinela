# evals/test_contratos.py
"""Pruebas unitarias de contratos Pydantic v2 (IDs, transiciones, unión discriminada, bitácora, etc.)."""

from datetime import date, datetime, timezone
import pytest
from pydantic import ValidationError

from contracts import (
    Accion,
    AccionLLM,
    AjustePrecio,
    Alerta,
    AlertaVista,
    Borrador,
    CentinelaConfig,
    CifraTrazable,
    CitaPolitica,
    ConfigKpi,
    ContactoCartera,
    DecisionRequest,
    DiagnosticoLLM,
    EntidadRef,
    EntradaBitacora,
    EstadoAlerta,
    Hallazgo,
    ImpactoCalculado,
    Kpi,
    Propuesta,
    PropuestaLLM,
    ResultadoEjecucion,
    Severidad,
    SimulacionResp,
    TipoEntidad,
    TrazaLLM,
    numeros_sueltos,
    transicion_valida,
    verificar_cadena,
)


def test_entidad_ref_valida():
    ref = EntidadRef(tipo=TipoEntidad.CLIENTE, id="C0496")
    assert ref.id == "C0496"

    ref_v = EntidadRef(tipo=TipoEntidad.VENDEDOR, id="V03")
    assert ref_v.id == "V03"

    ref_pr = EntidadRef(tipo=TipoEntidad.PROVEEDOR, id="PR08")
    assert ref_pr.id == "PR08"

    ref_p = EntidadRef(tipo=TipoEntidad.SKU, id="P0119")
    assert ref_p.id == "P0119"

    ref_bod = EntidadRef(tipo=TipoEntidad.BODEGA, id="BOD-MDE")
    assert ref_bod.id == "BOD-MDE"


def test_entidad_ref_invalida():
    with pytest.raises(ValidationError):
        EntidadRef(tipo=TipoEntidad.CLIENTE, id="INVALIDO")

    with pytest.raises(ValidationError):
        EntidadRef(tipo=TipoEntidad.VENDEDOR, id="C0001")


def test_transiciones_estado_alerta():
    assert transicion_valida(EstadoAlerta.NUEVA, EstadoAlerta.EN_ANALISIS)
    assert transicion_valida(EstadoAlerta.EN_ANALISIS, EstadoAlerta.PROPUESTA)
    assert transicion_valida(EstadoAlerta.PROPUESTA, EstadoAlerta.APROBADA)
    assert transicion_valida(EstadoAlerta.APROBADA, EstadoAlerta.EJECUTADA)

    # Transiciones inválidas
    assert not transicion_valida(EstadoAlerta.NUEVA, EstadoAlerta.APROBADA)
    assert not transicion_valida(EstadoAlerta.PROPUESTA, EstadoAlerta.EJECUTADA)
    assert not transicion_valida(EstadoAlerta.EJECUTADA, EstadoAlerta.NUEVA)


def test_alerta_avanzar():
    hallazgo = Hallazgo(
        hallazgo_id="H-12345678",
        kpi=Kpi.MARGEN,
        regla="OPE-POL-007/costo+5%",
        severidad=Severidad.ALTA,
        entidades=[EntidadRef(tipo=TipoEntidad.PROVEEDOR, id="PR08")],
        valor_observado=0.08,
        umbral=0.05,
        corte=date(2026, 8, 15),
        dinero_en_riesgo_cop=23558346,
        consulta_ids=["Q-123456789012"],
        huella_causa="costo|PR08",
    )

    alerta = Alerta(
        alerta_id="ALR-20260815-abcdef",
        estado=EstadoAlerta.NUEVA,
        huella_causa="costo|PR08",
        hallazgos=[hallazgo],
        severidad=Severidad.ALTA,
        dinero_en_riesgo_cop=23558346,
        corte_creacion=date(2026, 8, 15),
        creada_en=datetime.now(timezone.utc),
        version=1,
    )

    alerta2 = alerta.avanzar(EstadoAlerta.EN_ANALISIS)
    assert alerta2.estado == EstadoAlerta.EN_ANALISIS
    assert alerta2.version == 2

    with pytest.raises(ValueError):
        alerta2.avanzar(EstadoAlerta.APROBADA)


def test_numeros_sueltos():
    texto_limpio = "Se observó un incremento en la línea Hogar con proveedor PR08 y fecha 2026-08-15."
    assert numeros_sueltos(texto_limpio) == []

    texto_con_numeros = "Se observó un incremento de 15.5 por ciento en 4 productos."
    assert numeros_sueltos(texto_con_numeros) == ["15.5", "4"]


def test_diagnostico_llm_validacion():
    cifra = CifraTrazable(
        etiqueta="Incremento de costo PR08",
        valor=23558346.0,
        unidad="COP",
        consulta_id="Q-123456789012",
    )
    cita = CitaPolitica(
        documento="OPE-POL-007",
        seccion="4. Variaciones de costo",
        fragmento_hash="a" * 64,
    )

    # Válido: sin números sueltos en texto libre
    diag = DiagnosticoLLM(
        resumen="Incremento de costo en proveedor PR08 afecta cuatro productos de la linea Hogar.",
        causa_raiz="El proveedor PR08 actualizó tarifas según OPE-POL-007 sin reflejo oportuno en precios.",
        cifras=[cifra],
        politicas=[cita],
        supuestos=["Demanda constante"],
        evidencia_suficiente=True,
        confianza=0.9,
    )
    assert diag.confianza == 0.9

    # Inválido: números sueltos en causa raíz
    with pytest.raises(ValidationError):
        DiagnosticoLLM(
            resumen="Afecta cuatro productos.",
            causa_raiz="El costo subió 5 por ciento inesperadamente.",
            cifras=[cifra],
            politicas=[cita],
            evidencia_suficiente=True,
            confianza=0.9,
        )


def test_union_discriminada_acciones():
    accion_precio = AjustePrecio(skus=["P0119", "P0120"], pct_ajuste=7.5)
    assert accion_precio.tipo == "ajuste_precio"

    accion_cartera = ContactoCartera(cliente_id="C0496", nivel="llamada_acuerdo")
    assert accion_cartera.tipo == "contacto_cartera"

    # Verificamos PropuestaLLM con unión discriminada
    prop_llm = PropuestaLLM(
        acciones=[
            AccionLLM(
                titulo="Ajustar precio de lista",
                razon="Trasladar incremento de costo de proveedor PR08",
                parametros=accion_precio,
                confianza=0.95,
            )
        ]
    )
    assert len(prop_llm.acciones) == 1
    assert prop_llm.acciones[0].parametros.tipo == "ajuste_precio"


def test_decision_request_reglas():
    # Aprobar válido
    req_aprob = DecisionRequest(
        decision="aprobar",
        accion_ids=["ACC-12345678"],
        decidido_por="usuario:analista_financiero",
    )
    assert req_aprob.decision == "aprobar"

    # Rechazar exige motivo >= 10 chars
    with pytest.raises(ValidationError):
        DecisionRequest(
            decision="rechazar",
            motivo="corto",
            decidido_por="usuario:analista_financiero",
        )

    req_rech = DecisionRequest(
        decision="rechazar",
        motivo="Estrategia comercial acordó absorber el incremento este mes.",
        decidido_por="usuario:analista_financiero",
    )
    assert req_rech.decision == "rechazar"


def test_bitacora_cadena_y_manipulacion():
    t0 = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 15, 10, 1, 0, tzinfo=timezone.utc)

    e1 = EntradaBitacora.sellar(
        None,
        alerta_id="ALR-20260815-abcdef",
        evento="alerta_creada",
        actor="vigia",
        payload={"kpi": "margen_pct"},
        ts=t0,
    )
    assert e1.seq == 1
    assert e1.hash_prev == "0" * 64

    e2 = EntradaBitacora.sellar(
        e1,
        alerta_id="ALR-20260815-abcdef",
        evento="analisis_completo",
        actor="analista",
        payload={"cifras": 1},
        ts=t1,
    )
    assert e2.seq == 2
    assert e2.hash_prev == e1.hash

    assert verificar_cadena([e1, e2]) is True

    # Manipulación de contenido en e1
    e1_manipulada = e1.model_copy(update={"payload": {"kpi": "hackeado"}})
    assert verificar_cadena([e1_manipulada, e2]) is False


def test_contratos_nuevos_0_13():
    # 1. SimulacionResp
    sim_resp = SimulacionResp(
        run_id="run-sim-001",
        corte=date(2026, 8, 15),
        dias_avanzados=7,
        pipeline_disparado=True,
    )
    assert sim_resp.dias_avanzados == 7

    # 2. AlertaVista
    hallazgo = Hallazgo(
        hallazgo_id="H-12345678",
        kpi=Kpi.SALDO_VENCIDO,
        regla="FIN-POL-004/mora>15d",
        severidad=Severidad.ALTA,
        entidades=[EntidadRef(tipo=TipoEntidad.CLIENTE, id="C0496")],
        valor_observado=22.0,
        umbral=15.0,
        corte=date(2026, 9, 30),
        dinero_en_riesgo_cop=15000000,
        consulta_ids=["Q-123456789012"],
        huella_causa="cartera|C0496",
    )
    alerta = Alerta(
        alerta_id="ALR-20260930-123456",
        estado=EstadoAlerta.PROPUESTA,
        huella_causa="cartera|C0496",
        hallazgos=[hallazgo],
        severidad=Severidad.ALTA,
        dinero_en_riesgo_cop=15000000,
        corte_creacion=date(2026, 9, 30),
        creada_en=datetime.now(timezone.utc),
        version=1,
    )
    vista = AlertaVista(
        alerta=alerta,
        nombres_resueltos={"C0496": "Supermercado El Sol"},
    )
    assert vista.nombres_resueltos["C0496"] == "Supermercado El Sol"

    # 3. ConfigKpi
    config_kpi = ConfigKpi(
        kpi=Kpi.MARGEN,
        nombre="Margen Mínimo por Línea",
        umbral_defecto=0.15,
        umbral_actual=0.12,
        responsable_email="gerencia.comercial@distribuidoraandina.com",
        autonomia="propone",
        activo=True,
    )
    assert config_kpi.autonomia == "propone"

    # 4. CentinelaConfig
    cfg = CentinelaConfig(
        clave="kpi_margen",
        valor={"umbral": 0.12, "activo": True},
        actualizado_en=datetime.now(timezone.utc),
        actualizado_por="usuario:administrador",
    )
    assert cfg.clave == "kpi_margen"
