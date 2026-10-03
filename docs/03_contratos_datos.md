# 03 · Contratos, handshakes y estructuras de datos (Pydantic v2)

Todos los mensajes entre componentes son modelos **Pydantic v2** con `extra="forbid"`. El mismo modelo sirve como: (1) validación de entrada/salida de la API, (2) esquema de *tool use* de Bedrock (`Model.model_json_schema()`), (3) formato de persistencia en DynamoDB y (4) fixture de las evals. Código destino: `backend/contracts/`. El código de este documento se probó (ver §9).

## 0. Reglas de diseño
1. **Dos fases para todo lo que toca dinero.** El LLM produce un *borrador* (`*LLM`) **sin cifras de impacto**; el servidor lo completa con números calculados (`ImpactoCalculado`). El modelo nunca escribe un monto.
2. **Las cifras viajan en `CifraTrazable`** (valor + unidad + `consulta_id`). El texto libre no debe contener números sueltos; `numeros_sueltos()` los detecta y fuerza un reintento. Regla estricta a propósito: hasta los conteos pequeños se escriben con letras ("cuatro SKU"), porque una prueba real mostró que "4 SKU" se marca; el prompt del sistema lo indica.
3. **Privacidad por construcción:** los contratos que ve el LLM usan **IDs** (`V03`, `C0496`), nunca nombres de personas. Los nombres se resuelven en la capa API para la UI.
4. **Mensajes inmutables** (`frozen=True`); un cambio de estado crea una copia nueva.
5. **Versionado:** todo mensaje persistido lleva `schema_version`.
6. **Contrato antes que código:** si un campo no está aquí, no cruza una frontera.

## 1. Tipos base y vocabulario

```python
# backend/contracts/base.py
import hashlib
import json
import re
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0"


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def _id(pattern: str):
    return Annotated[str, StringConstraints(pattern=pattern)]


ClienteId = _id(r"^C\d{4}$")
SkuId = _id(r"^P\d{4}$")
VendedorId = _id(r"^V\d{2}$")
ProveedorId = _id(r"^PR\d{2}$")
BodegaId = _id(r"^BOD-[A-Z]{3}$")
OcId = _id(r"^OC-\d{6}$")
AlertaId = _id(r"^ALR-\d{8}-[0-9a-f]{6}$")   # ALR-<corte yyyymmdd>-<6 hex>
ConsultaId = _id(r"^Q-[0-9a-f]{12}$")
AccionId = _id(r"^ACC-[0-9a-f]{8}$")
Hash256 = _id(r"^[0-9a-f]{64}$")
Pesos = int                                    # COP enteros
Confianza = Annotated[float, Field(ge=0.0, le=1.0)]
CERO_HASH = "0" * 64


class Kpi(StrEnum):
    MARGEN = "margen_pct"
    SALDO_VENCIDO = "saldo_vencido"
    DIAS_PAGO = "dias_pago_prom"
    COBERTURA = "cobertura_dias"
    DESCUENTO_EXCESO = "descuento_en_exceso"
    INTERVALO_COMPRA = "veces_intervalo_habitual"
    VENTA_BAJO_COSTO = "venta_bajo_costo"        # regla extra (COM-POL-002 §4)


class Vista(StrEnum):
    VENTAS = "v_ventas"
    MARGEN_SEMANAL = "v_margen_semanal_linea"
    CARTERA = "v_cartera_cliente"
    DIAS_PAGO = "v_dias_pago_mensual"
    COBERTURA = "v_cobertura_inventario"
    DESCUENTOS = "v_descuentos_fuera_politica"
    ACTIVIDAD = "v_actividad_cliente"


class Severidad(StrEnum):
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class EstadoAlerta(StrEnum):
    NUEVA = "nueva"
    EN_ANALISIS = "en_analisis"
    PROPUESTA = "propuesta"
    SIN_EVIDENCIA = "sin_evidencia"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    EJECUTADA = "ejecutada"
    FALLIDA = "fallida"


TRANSICIONES: dict[EstadoAlerta, set[EstadoAlerta]] = {
    EstadoAlerta.NUEVA: {EstadoAlerta.EN_ANALISIS, EstadoAlerta.FALLIDA},
    EstadoAlerta.EN_ANALISIS: {EstadoAlerta.PROPUESTA, EstadoAlerta.SIN_EVIDENCIA, EstadoAlerta.FALLIDA},
    EstadoAlerta.PROPUESTA: {EstadoAlerta.APROBADA, EstadoAlerta.RECHAZADA},
    EstadoAlerta.APROBADA: {EstadoAlerta.EJECUTADA, EstadoAlerta.FALLIDA},
    EstadoAlerta.SIN_EVIDENCIA: set(),
    EstadoAlerta.RECHAZADA: set(),
    EstadoAlerta.EJECUTADA: set(),
    EstadoAlerta.FALLIDA: {EstadoAlerta.NUEVA},     # reintento manual
}


class TipoEntidad(StrEnum):
    CLIENTE = "cliente"
    VENDEDOR = "vendedor"
    PROVEEDOR = "proveedor"
    SKU = "sku"
    BODEGA = "bodega"
    LINEA = "linea"
    SEGMENTO = "segmento"


_PATRON_ENTIDAD = {
    TipoEntidad.CLIENTE: r"^C\d{4}$", TipoEntidad.VENDEDOR: r"^V\d{2}$", TipoEntidad.PROVEEDOR: r"^PR\d{2}$",
    TipoEntidad.SKU: r"^P\d{4}$", TipoEntidad.BODEGA: r"^BOD-[A-Z]{3}$",
}


class EntidadRef(Contrato):
    """Referencia por ID. Nunca lleva nombre de persona."""
    tipo: TipoEntidad
    id: str

    @model_validator(mode="after")
    def _formato(self):
        patron = _PATRON_ENTIDAD.get(self.tipo)
        if patron and not re.match(patron, self.id):
            raise ValueError(f"id '{self.id}' no corresponde a tipo {self.tipo}")
        return self


def transicion_valida(origen: EstadoAlerta, destino: EstadoAlerta) -> bool:
    return destino in TRANSICIONES[origen]
```

## 2. Evidencia trazable

```python
# backend/contracts/evidencia.py
Unidad = Literal["COP", "%", "pp", "dias", "unidades", "veces", "lineas"]


class ConsultaRegistrada(Contrato):
    """Una consulta ejecutada por una herramienta. Se guarda en `trazas` y se muestra en 'Cómo llegué aquí'."""
    consulta_id: ConsultaId
    vista: Vista
    sql_renderizado: str
    corte: date
    filas: int = Field(ge=0)
    resultado_hash: Hash256
    ejecutada_en: datetime


class CifraTrazable(Contrato):
    etiqueta: str = Field(max_length=80)
    valor: float
    unidad: Unidad
    consulta_id: ConsultaId


class CitaPolitica(Contrato):
    documento: Literal["FIN-POL-004", "COM-POL-002", "OPE-POL-007"]
    seccion: str = Field(max_length=60)                  # p. ej. "4. Seguimiento y escalamiento"
    fragmento_hash: Hash256                              # hash del texto recuperado de la KB


_ID_O_FECHA = re.compile(r"\b(?:P\d{4}|C\d{4}|V\d{2}|PR\d{2}|OC-\d{6}|BOD-[A-Z]{3}|ALR-[\w-]+|FIN-POL-\d+|COM-POL-\d+|OPE-POL-\d+)\b|\d{4}-\d{2}-\d{2}")


def numeros_sueltos(texto: str) -> list[str]:
    """Números en texto libre (fuera de IDs y fechas). El pipeline reintenta una vez si hay alguno."""
    return re.findall(r"\d[\d.,]*", _ID_O_FECHA.sub(" ", texto))
```

## 3. Vigía → Alerta

```python
# backend/contracts/alertas.py
class Hallazgo(Contrato):
    """Salida determinista del Vigía (sin LLM)."""
    hallazgo_id: str = Field(pattern=r"^H-[0-9a-f]{8}$")
    kpi: Kpi
    regla: str                                  # p. ej. "OPE-POL-007/costo+5%"
    severidad: Severidad
    entidades: list[EntidadRef] = Field(min_length=1)
    valor_observado: float
    umbral: float
    corte: date
    dinero_en_riesgo_cop: Pesos = Field(ge=0)
    consulta_ids: list[ConsultaId] = Field(min_length=1)
    huella_causa: str                           # clave de dedup: kpi + entidad raíz (p. ej. "costo|PR08")


class Alerta(Contrato):
    schema_version: str = SCHEMA_VERSION
    alerta_id: AlertaId
    estado: EstadoAlerta
    huella_causa: str
    hallazgos: list[Hallazgo] = Field(min_length=1)
    severidad: Severidad
    dinero_en_riesgo_cop: Pesos = Field(ge=0)
    corte_creacion: date
    creada_en: datetime
    version: int = Field(ge=1)                  # bloqueo optimista en DynamoDB

    def avanzar(self, destino: EstadoAlerta) -> "Alerta":
        if not transicion_valida(self.estado, destino):
            raise ValueError(f"transición inválida {self.estado} → {destino}")
        return self.model_copy(update={"estado": destino, "version": self.version + 1})
```

## 4. Analista y Estratega (contratos del LLM)

```python
# backend/contracts/agentes.py
class DiagnosticoLLM(Contrato):
    """Esquema de la herramienta `emitir_diagnostico` (tool use de Haiku 4.5)."""
    resumen: str = Field(max_length=220)                # una frase para la bandeja
    causa_raiz: str = Field(max_length=800)
    cifras: list[CifraTrazable]
    politicas: list[CitaPolitica]
    supuestos: list[str] = Field(default_factory=list, max_length=5)
    evidencia_suficiente: bool
    confianza: Confianza

    @model_validator(mode="after")
    def _coherencia(self):
        if self.evidencia_suficiente and not self.cifras:
            raise ValueError("con evidencia suficiente se requiere al menos una cifra trazable")
        if not self.evidencia_suficiente and self.confianza > 0.4:
            raise ValueError("sin evidencia suficiente la confianza no puede superar 0.4")
        if numeros_sueltos(self.resumen + " " + self.causa_raiz):
            raise ValueError("el texto contiene números fuera de `cifras`")
        return self


# --- Parámetros de acción: unión discriminada por `tipo` (lista cerrada de herramientas del Ejecutor) ---
class AjustePrecio(Contrato):
    tipo: Literal["ajuste_precio"] = "ajuste_precio"
    skus: list[SkuId] = Field(min_length=1, max_length=20)
    pct_ajuste: Annotated[float, Field(gt=0, le=30)]


class ContactoCartera(Contrato):
    tipo: Literal["contacto_cartera"] = "contacto_cartera"
    cliente_id: ClienteId
    nivel: Literal["recordatorio", "llamada_acuerdo", "solo_contado", "bloqueo_despachos"]


class ExpeditarOC(Contrato):
    tipo: Literal["expeditar_oc"] = "expeditar_oc"
    oc_id: OcId
    proveedor_id: ProveedorId
    sku: SkuId
    bodega_id: BodegaId
    via: Literal["contactar_proveedor", "proveedor_alterno", "entrega_parcial"]


class RevisionDescuentos(Contrato):
    tipo: Literal["revision_descuentos"] = "revision_descuentos"
    vendedor_id: VendedorId
    medida: Literal["revision_previa_cotizacion", "suspender_facultad_cotizar"]


class ReactivarCliente(Contrato):
    tipo: Literal["reactivar_cliente"] = "reactivar_cliente"
    cliente_id: ClienteId
    vendedor_id: VendedorId
    canal: Literal["visita", "llamada", "oferta"]


class CorregirVentaBajoCosto(Contrato):
    tipo: Literal["corregir_venta_bajo_costo"] = "corregir_venta_bajo_costo"
    skus: list[SkuId] = Field(min_length=1, max_length=20)


ParametrosAccion = Annotated[
    Union[AjustePrecio, ContactoCartera, ExpeditarOC, RevisionDescuentos, ReactivarCliente, CorregirVentaBajoCosto],
    Field(discriminator="tipo"),
]


class AccionLLM(Contrato):
    titulo: str = Field(max_length=120)
    razon: str = Field(max_length=400)
    parametros: ParametrosAccion
    confianza: Confianza


class PropuestaLLM(Contrato):
    """Esquema de la herramienta `emitir_propuesta`. NO contiene montos."""
    acciones: list[AccionLLM] = Field(min_length=1, max_length=3)


class ImpactoCalculado(Contrato):
    """Lo produce `calcular_impacto` (Python/SQL). El LLM solo lo ve, no lo escribe."""
    valor_cop: Pesos
    horizonte: Literal["mensual", "unico"]
    metodo: str                                  # p. ej. "unidades_30d x delta_costo"
    intervalo_cop: tuple[Pesos, Pesos] | None = None
    consulta_ids: list[ConsultaId] = Field(min_length=1)


class Accion(Contrato):
    accion_id: AccionId
    titulo: str
    razon: str
    parametros: ParametrosAccion
    confianza: Confianza
    impacto: ImpactoCalculado


class Propuesta(Contrato):
    schema_version: str = SCHEMA_VERSION
    alerta_id: AlertaId
    diagnostico: DiagnosticoLLM
    acciones: list[Accion] = Field(min_length=1, max_length=3)
    modelo: str                                  # inference profile usado
    generada_en: datetime
```

## 5. Decisión humana y Ejecutor

```python
# backend/contracts/decision.py
class DecisionRequest(Contrato):
    """POST /alertas/{id}/decision. Cabecera obligatoria: Idempotency-Key."""
    decision: Literal["aprobar", "editar", "rechazar"]
    accion_ids: list[AccionId] = Field(default_factory=list)
    ediciones: dict[AccionId, ParametrosAccion] = Field(default_factory=dict)
    motivo: str | None = Field(default=None, max_length=500)
    decidido_por: str = Field(pattern=r"^usuario:[a-z0-9_.-]{2,30}$")

    @model_validator(mode="after")
    def _reglas(self):
        if self.decision == "rechazar" and len((self.motivo or "").strip()) < 10:
            raise ValueError("rechazar exige un motivo de al menos 10 caracteres")
        if self.decision == "editar" and not self.ediciones:
            raise ValueError("editar exige al menos una edición")
        if self.decision in ("aprobar", "editar") and not self.accion_ids:
            raise ValueError("aprobar o editar exige accion_ids")
        return self


class Borrador(Contrato):
    artefacto_id: str = Field(pattern=r"^ART-[0-9a-f]{8}$")
    accion_id: AccionId
    tipo: Literal["correo", "tarea", "orden_compra"]
    destino: str = Field(pattern=r"^sandbox://")        # nunca un destino real
    contenido: str = Field(max_length=4000)
    estado: Literal["borrador"] = "borrador"


class ResultadoEjecucion(Contrato):
    alerta_id: AlertaId
    borradores: list[Borrador]
    ok: bool
    error: str | None = None
```

## 6. Bitácora inmutable (hash encadenado)

```python
# backend/contracts/bitacora.py
class Evento(StrEnum):
    ALERTA_CREADA = "alerta_creada"
    ANALISIS_COMPLETO = "analisis_completo"
    PROPUESTA_GENERADA = "propuesta_generada"
    DECISION_HUMANA = "decision_humana"
    ACCION_EJECUTADA = "accion_ejecutada"
    GUARDRAIL_INTERVINO = "guardrail_intervino"
    ERROR = "error"


def canonico(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


class EntradaBitacora(Contrato):
    schema_version: str = SCHEMA_VERSION
    alerta_id: AlertaId
    seq: int = Field(ge=1)
    evento: Evento
    actor: str = Field(pattern=r"^(sistema|vigia|analista|estratega|ejecutor|usuario:[a-z0-9_.-]{2,30})$")
    payload: dict
    ts: datetime
    hash_prev: Hash256
    hash: Hash256

    @staticmethod
    def calcular(hash_prev, alerta_id, seq, evento, actor, payload, ts) -> str:
        base = canonico([hash_prev, alerta_id, seq, str(evento), actor, payload, ts.isoformat()])
        return hashlib.sha256(base.encode()).hexdigest()

    @classmethod
    def sellar(cls, previa: "EntradaBitacora | None", *, alerta_id, evento, actor, payload, ts):
        hash_prev = previa.hash if previa else CERO_HASH
        seq = previa.seq + 1 if previa else 1
        h = cls.calcular(hash_prev, alerta_id, seq, evento, actor, payload, ts)
        return cls(alerta_id=alerta_id, seq=seq, evento=evento, actor=actor, payload=payload,
                   ts=ts, hash_prev=hash_prev, hash=h)


def verificar_cadena(entradas: list[EntradaBitacora]) -> bool:
    prev = None
    for e in sorted(entradas, key=lambda x: x.seq):
        esperado = CERO_HASH if prev is None else prev.hash
        if e.hash_prev != esperado or e.seq != (1 if prev is None else prev.seq + 1):
            return False
        if e.hash != EntradaBitacora.calcular(e.hash_prev, e.alerta_id, e.seq, e.evento, e.actor, e.payload, e.ts):
            return False
        prev = e
    return True
```

## 7. Trazas, chat y errores

```python
# backend/contracts/operacion.py
class TrazaLLM(Contrato):
    """Una llamada a Bedrock. Alimenta `trazas` (costo por alerta) y las métricas EMF."""
    run_id: str
    alerta_id: AlertaId | None = None
    agente: Literal["analista", "estratega", "chat"]
    modelo: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    tokens_cache_lectura: int = Field(default=0, ge=0)
    latencia_ms: int = Field(ge=0)
    costo_usd: float = Field(ge=0)
    guardrail_intervino: bool = False
    consulta_ids: list[ConsultaId] = Field(default_factory=list)
    reintentos: int = Field(default=0, ge=0)
    error: str | None = None
    ts: datetime


class ChatRequest(Contrato):
    alerta_id: AlertaId | None = None                    # chat anclado o libre
    mensaje: str = Field(min_length=1, max_length=2000)


class ChatToken(Contrato):
    evento: Literal["token"] = "token"
    texto: str


class ChatCifra(Contrato):
    evento: Literal["cifra"] = "cifra"
    cifra: CifraTrazable


class ChatFin(Contrato):
    evento: Literal["fin"] = "fin"
    consulta_ids: list[ConsultaId]
    costo_usd: float


class ChatError(Contrato):
    evento: Literal["error"] = "error"
    codigo: str
    mensaje: str


ChatEvento = Annotated[Union[ChatToken, ChatCifra, ChatFin, ChatError], Field(discriminator="evento")]


class ErrorAPI(Contrato):
    codigo: Literal["validacion", "no_encontrado", "transicion_invalida", "conflicto_version",
                    "sin_evidencia", "guardrail_bloqueo", "limite_costo", "interno"]
    mensaje: str
    request_id: str
    detalle: dict | None = None
```

## 8. Contratos de herramientas (FastMCP) y handshakes

### 8.1 Herramientas (lista cerrada; sin SQL libre)
```python
# backend/contracts/herramientas.py
class Filtro(Contrato):
    columna: str = Field(pattern=r"^[a-z_]{1,40}$")
    op: Literal["=", "!=", "<", "<=", ">", ">=", "in"]
    valor: str | int | float | list[str | int | float]


class ConsultarVistaIn(Contrato):
    vista: Vista
    columnas: list[str] = Field(min_length=1, max_length=20)
    filtros: list[Filtro] = Field(default_factory=list, max_length=8)
    agrupar_por: list[str] = Field(default_factory=list, max_length=4)
    ordenar_por: str | None = None
    limite: int = Field(default=100, ge=1, le=500)


class ConsultarVistaOut(Contrato):
    consulta: ConsultaRegistrada
    columnas: list[str]
    filas: list[list[str | int | float | None]]
    truncado: bool


class BuscarPoliticaIn(Contrato):
    consulta: str = Field(min_length=3, max_length=300)
    k: int = Field(default=3, ge=1, le=5)


class FragmentoPolitica(Contrato):
    documento: Literal["FIN-POL-004", "COM-POL-002", "OPE-POL-007"]
    seccion: str
    texto: str                                   # se inyecta al LLM dentro de <datos_politica>…</datos_politica>
    score: float = Field(ge=0, le=1)
    fragmento_hash: Hash256


class BuscarPoliticaOut(Contrato):
    fragmentos: list[FragmentoPolitica]
    guardrail_ataque_detectado: bool = False     # resultado de ApplyGuardrail sobre los fragmentos


class CalcularImpactoIn(Contrato):
    metodo: Literal["delta_costo_x_unidades_30d", "exceso_descuento", "cartera_vencida_en_riesgo",
                    "margen_perdido_bajo_costo", "ventas_perdidas_cliente_inactivo", "ventas_perdidas_quiebre"]
    parametros: dict[str, str | int | float | list[str]]


class CrearBorradorIn(Contrato):
    alerta_id: AlertaId
    accion_id: AccionId                          # el Ejecutor solo acepta acciones en estado `aprobada`
```

### 8.2 Handshakes (protocolos entre componentes)

| # | Frontera | Mensaje de ida | Mensaje de vuelta | Reglas del handshake |
|---|---|---|---|---|
| H1 | UI → API (reloj) | `POST /simulacion/avanzar?dias=n` + `x-api-key`, `x-request-id` | `202` `{run_id, corte}` (`SimulacionResp`) | Responde en <1 s; el pipeline corre asíncrono. Mismo `x-request-id` = misma ejecución (idempotente). |
| H2 | API → Pipeline | Auto-invocación `Event`: `PipelineEvent{run_id, accion:"vigia"\|"reanudar", corte, alerta_id?}` | (ninguna) | Reintentos de Lambda ≤ 2 con DLQ SQS; el pipeline es idempotente por `(run_id, alerta_id)`. |
| H3 | UI → API (estado) | `GET /alertas?estado=` (polling 2 s) | `list[AlertaVista]` (Alerta + nombres resueltos) | La UI ve `nueva → en_analisis → propuesta`. `ETag` = `version`. |
| H4 | Agente → Herramienta | `ConsultarVistaIn` / `BuscarPoliticaIn` / `CalcularImpactoIn` | `…Out` con `ConsultaRegistrada` | Validador: solo vistas `v_*`, columnas permitidas, `LIMIT` forzado; cada llamada deja `ConsultaRegistrada` en `trazas`. |
| H5 | Agente → Bedrock | `Converse` con `toolConfig` (esquema = `DiagnosticoLLM`/`PropuestaLLM`) + `guardrailConfig` | tool-use validado con Pydantic | Si falla la validación: **1 reintento** devolviendo el error al modelo; si falla otra vez → estado `sin_evidencia` y bitácora `error`. |
| H6 | Pipeline → Humano (HITL) | LangGraph `interrupt(InterruptPayload{alerta_id, propuesta})`; estado `propuesta` | `DecisionRequest` + `Idempotency-Key` | La Lambda termina; no hay cómputo mientras se espera. Al llegar la decisión se invoca `PipelineEvent{accion:"reanudar"}` → `Command(resume=decision)`. |
| H7 | UI → API (decisión) | `POST /alertas/{id}/decision` | `200 Alerta` o `ErrorAPI` | `409 conflicto_version` si `If-Match` ≠ `version`; `409 transicion_invalida` si no está en `propuesta`; reintento con la misma `Idempotency-Key` devuelve el mismo resultado. |
| H8 | Pipeline → Ejecutor | `CrearBorradorIn` | `ResultadoEjecucion` | Solo si estado = `aprobada`; destinos `sandbox://`; cada borrador sella una `EntradaBitacora`. |
| H9 | UI → API (chat, SSE) | `POST /chat` `ChatRequest` | stream `ChatEvento` (`token`\|`cifra`\|`fin`\|`error`), `Content-Type: text/event-stream` | La respuesta final siempre cierra con `fin` (consultas y costo); sin evidencia → texto "no tengo evidencia suficiente". |
| H10 | Cualquiera → Bitácora | `EntradaBitacora.sellar(previa, …)` | entrada con `hash` | `PutItem` condicional `attribute_not_exists(seq)`; IAM Deny de `UpdateItem`/`DeleteItem`; `GET /bitacora?verificar=true` ejecuta `verificar_cadena`. |

### 8.3 Estado del grafo (LangGraph)
```python
class EstadoGrafo(Contrato):
    run_id: str
    corte: date
    alerta_id: AlertaId | None = None
    hallazgos: list[Hallazgo] = Field(default_factory=list)
    diagnostico: DiagnosticoLLM | None = None
    propuesta: Propuesta | None = None
    decision: DecisionRequest | None = None
    resultado: ResultadoEjecucion | None = None


class InterruptPayload(Contrato):
    alerta_id: AlertaId
    propuesta: Propuesta


class PipelineEvent(Contrato):
    run_id: str
    accion: Literal["vigia", "reanudar"]
    corte: date
    alerta_id: AlertaId | None = None
```
(`EstadoGrafo` es mutable en la práctica: LangGraph reemplaza el objeto en cada nodo; al ser `frozen`, cada nodo devuelve una copia con `model_copy(update=…)`.)

### 8.4 Claves de DynamoDB

| Tabla | PK | SK | GSI | Contenido |
|---|---|---|---|---|
| `centinela_alertas` | `alerta_id` | `META` | `gsi_estado` (`estado`, `dinero_en_riesgo_cop`) | `Alerta` + `Propuesta` serializada; `version` para bloqueo optimista; clave de dedup `huella_causa` (GSI `gsi_huella`) |
| `centinela_bitacora` | `alerta_id` | `seq` (número) | — | `EntradaBitacora` |
| `centinela_checkpoints` | `thread_id` (=`alerta_id`) | `checkpoint_id` | — | Estado LangGraph (`EstadoGrafo`) |
| `centinela_trazas` | `alerta_id` (o `CHAT#<run_id>`) | `ts#tipo` | — | `TrazaLLM` y `ConsultaRegistrada`; TTL 30 días |
| `centinela_reloj` | `RELOJ` | `ACTUAL` | — | `{corte, run_id}` |

## 9. Verificación
El código de las secciones 1-8 se extrajo y se ejecutó con `pydantic` v2: validación de IDs, transiciones de estado, unión discriminada de acciones, reglas de `DecisionRequest`, rechazo de números sueltos, cadena de bitácora (incluida la detección de manipulación) y esquema JSON de herramientas. Al crear `backend/contracts/`, estas pruebas pasan a `evals/test_contratos.py`.
