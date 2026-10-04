# evals/test_contratos.py
"""Pruebas unitarias de contratos Pydantic v2 (IDs, transiciones, unión discriminada, bitácora, etc.)."""

from datetime import date, datetime, timezone
import pytest
from pydantic import ValidationError

from contracts import (
    Accion,
    AjustePrecio,
    Alerta,
    AlertaVista,
    Borrador,
    CifraTrazable,
    CitaPolitica,
    ConfiguracionUpdate,
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
    SeleccionAccion,
    SeleccionEstratega,
    numeros_en,
    renderizar_texto,
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

    # Válido: las cifras se citan con marcadores {cN}, sin números propios en el texto
    diag = DiagnosticoLLM(
        resumen="Incremento de costo en proveedor PR08: {c1} de alza en la linea Hogar.",
        causa_raiz="El proveedor PR08 actualizó tarifas según OPE-POL-007 sin reflejo oportuno en precios.",
        cifras=[cifra],
        politicas=[cita],
        supuestos=["Demanda constante"],
        evidencia_suficiente=True,
        confianza=0.9,
    )
    assert diag.confianza == 0.9

    # Inválido: números sueltos (dígitos o palabras) o marcadores inexistentes
    for resumen, causa in [
        ("Afecta cuatro productos.", "El costo subió inesperadamente."),
        ("Subió.", "El costo subió 5 por ciento inesperadamente."),
        ("Subió {c1}.", "Y también {c7}."),
    ]:
        with pytest.raises(ValidationError):
            DiagnosticoLLM(resumen=resumen, causa_raiz=causa, cifras=[cifra], politicas=[cita], evidencia_suficiente=True, confianza=0.9)

    # Excepción: dígitos que aparecen literalmente en la política citada (umbrales)
    ok = DiagnosticoLLM(
        resumen="Costo sobre el umbral de 5 % de OPE-POL-007 §4.",
        causa_raiz="Comercial debe revisar el precio en 10 días hábiles.",
        cifras=[cifra], politicas=[cita], numeros_politica=["5", "10"], evidencia_suficiente=True, confianza=0.9,
    )
    assert ok.numeros_politica == ["5", "10"]
    with pytest.raises(ValidationError):   # las palabras de número nunca se permiten
        DiagnosticoLLM(resumen="Umbral de cinco por ciento.", causa_raiz="Sin más.", cifras=[cifra], politicas=[cita], numeros_politica=["5"], evidencia_suficiente=True, confianza=0.9)


def test_renderizado_de_cifras_y_numeros_de_politica():
    cifras = [
        CifraTrazable(etiqueta="Alza", valor=25.0, unidad="%", consulta_id="Q-123456789012"),
        CifraTrazable(etiqueta="Sobrecosto", valor=23522184, unidad="COP", consulta_id="Q-123456789012"),
        CifraTrazable(etiqueta="SKU", valor=4, unidad="skus", consulta_id="Q-123456789012"),
        CifraTrazable(etiqueta="Cobertura", valor=3.5, unidad="dias", consulta_id="Q-123456789012"),
    ]
    assert renderizar_texto("Subió {c1}, sobrecosto {c2}.", cifras) == "Subió 25 %, sobrecosto $23.522.184."
    assert renderizar_texto("afecta {c3} SKU", cifras) == "afecta 4 SKU"       # no duplica la unidad
    assert renderizar_texto("cobertura de {c4}", cifras) == "cobertura de 3,5 días"
    assert numeros_en("más de 5% en 10 días hábiles, 1.518 unidades") == ["1.518", "10", "5"]


def test_union_discriminada_acciones():
    accion_precio = AjustePrecio(skus=["P0119", "P0120"], pct_ajuste=7.5)
    assert accion_precio.tipo == "ajuste_precio"

    accion_cartera = ContactoCartera(cliente_id="C0496", nivel="llamada_acuerdo")
    assert accion_cartera.tipo == "contacto_cartera"

    # El modelo solo elige candidatas por número y las justifica, sin números propios
    sel = SeleccionEstratega(
        selecciones=[SeleccionAccion(candidato=1, titulo="Ajustar el precio de lista", razon="Trasladar el alza de {c1} al precio.", confianza=0.95)]
    )
    assert sel.selecciones[0].candidato == 1
    with pytest.raises(ValidationError):
        SeleccionEstratega(selecciones=[SeleccionAccion(candidato=1, titulo="Ajustar", razon="Subir el precio 11 %.", confianza=0.9)])
    with pytest.raises(ValidationError):   # el mismo candidato dos veces
        SeleccionEstratega(selecciones=[
            SeleccionAccion(candidato=2, titulo="A", razon="uno.", confianza=0.9),
            SeleccionAccion(candidato=2, titulo="B", razon="dos.", confianza=0.9),
        ])


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
        alertas_detectadas=12,
        alertas_nuevas=3,
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

    # 3. ConfiguracionUpdate
    upd = ConfiguracionUpdate(
        umbrales={"dias_mora": 20},
        autonomia={"ajuste_precio": "propone"},
        actor="usuario:administrador",
    )
    assert upd.umbrales["dias_mora"] == 20
    with pytest.raises(ValidationError):
        ConfiguracionUpdate(autonomia={"ajuste_precio": "libre"}, actor="usuario:administrador")
