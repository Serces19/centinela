# backend/services/persistencia.py
"""Servicio de persistencia DynamoDB para Centinela.

Gestiona las tablas:
- centinela_alertas: Alertas generadas con clave de dedup y bloqueo optimista.
- centinela_bitacora: Cadena inmutable de auditoría con hash SHA-256.
- centinela_reloj: Estado del reloj de simulación temporal.
- centinela_config: Configuración dinámica de KPIs.
- centinela_trazas: Trazas LLM y llamadas a herramientas (TTL 30d).
- centinela_checkpoints: Puntos de control LangGraph.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from contracts.agentes import Propuesta
from contracts.alertas import Alerta
from contracts.base import AlertaId, EstadoAlerta
from contracts.bitacora import EntradaBitacora, Evento
from contracts.configuracion import CORTE_INICIAL_LIMPIO
from contracts.decision import ResultadoEjecucion
from contracts.evidencia import ConsultaRegistrada
from contracts.operacion import TrazaLLM

logger = logging.getLogger("centinela.persistencia")


class PersistenciaService:
    """Gestiona operaciones de lectura y escritura en DynamoDB con fallback en memoria opcional."""

    def __init__(self, region_name: str | None = None, use_memory: bool | None = None):
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        if use_memory is None:
            backend_env = os.environ.get("CENTINELA_PERSISTENCIA_BACKEND", "dynamodb").lower()
            self.use_memory = (backend_env == "memory")
        else:
            self.use_memory = use_memory

        self._mem_alertas: dict[str, dict] = {}
        self._mem_bitacora: dict[str, list[EntradaBitacora]] = {}
        self._mem_trazas: dict[str, list[dict]] = {}
        self._mem_propuestas: dict[str, dict] = {}
        self._mem_resultados: dict[str, dict] = {}
        self._mem_feedback: list[dict] = []
        self._mem_config: dict[str, dict] = {}
        self._mem_consultas: dict[str, dict] = {}
        self._mem_reloj: dict[str, Any] = {
            "corte": CORTE_INICIAL_LIMPIO,
            "run_id": "bootstrap",
            "actualizado_en": datetime.now(timezone.utc).isoformat(),
        }

        if not self.use_memory:
            try:
                self.dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
                self.tbl_alertas = self.dynamodb.Table("centinela_alertas")
                self.tbl_bitacora = self.dynamodb.Table("centinela_bitacora")
                self.tbl_reloj = self.dynamodb.Table("centinela_reloj")
                self.tbl_config = self.dynamodb.Table("centinela_config")
                self.tbl_trazas = self.dynamodb.Table("centinela_trazas")
                self.tbl_checkpoints = self.dynamodb.Table("centinela_checkpoints")
            except Exception as e:
                logger.warning(f"No se pudo inicializar cliente DynamoDB ({e}). Usando modo memoria.")
                self.use_memory = True

    # -------------------------------------------------------------------------
    # centinela_alertas
    # -------------------------------------------------------------------------
    def guardar_alerta(self, alerta: Alerta) -> bool:
        """Guarda una alerta en centinela_alertas.

        Usa PutItem condicional sobre `alerta_id` para evitar duplicar si ya existe.
        Retorna True si fue creada, False si ya existía.
        """
        if self.use_memory:
            if alerta.alerta_id in self._mem_alertas:
                return False
            self._mem_alertas[alerta.alerta_id] = alerta.model_dump(mode="json")
            return True

        item = {
            "alerta_id": alerta.alerta_id,
            "tipo_registro": "META",
            "estado": alerta.estado.value,
            "dinero_en_riesgo_cop": Decimal(str(alerta.dinero_en_riesgo_cop)),
            "huella_causa": alerta.huella_causa,
            "severidad": alerta.severidad.value,
            "corte_creacion": alerta.corte_creacion.isoformat(),
            "creada_en": alerta.creada_en.isoformat(),
            "version": alerta.version,
            "payload": json.dumps(alerta.model_dump(mode="json")),
        }

        try:
            self.tbl_alertas.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(alerta_id)",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def obtener_alerta(self, alerta_id: str) -> Alerta | None:
        """Recupera una alerta por su ID."""
        if self.use_memory:
            raw = self._mem_alertas.get(alerta_id)
            if not raw:
                return None
            return Alerta.model_validate(raw)

        try:
            resp = self.tbl_alertas.get_item(
                Key={"alerta_id": alerta_id, "tipo_registro": "META"}
            )
            item = resp.get("Item")
            if not item:
                return None
            payload = json.loads(item["payload"])
            return Alerta.model_validate(payload)
        except ClientError as e:
            logger.error(f"Error consultando alerta {alerta_id}: {e}")
            raise

    def listar_alertas(self, estado: str | None = None) -> list[Alerta]:
        """Lista alertas, opcionalmente filtradas por estado."""
        if self.use_memory:
            res: list[Alerta] = []
            for raw in self._mem_alertas.values():
                alerta = Alerta.model_validate(raw)
                if estado is None or alerta.estado.value == estado:
                    res.append(alerta)
            res.sort(key=lambda a: a.dinero_en_riesgo_cop, reverse=True)
            return res

        try:
            if estado:
                from boto3.dynamodb.conditions import Key
                resp = self.tbl_alertas.query(
                    IndexName="gsi_estado",
                    KeyConditionExpression=Key("estado").eq(estado),
                    ScanIndexForward=False,  # dinero_en_riesgo descendente
                )
                items = resp.get("Items", [])
                while "LastEvaluatedKey" in resp:
                    resp = self.tbl_alertas.query(
                        IndexName="gsi_estado",
                        KeyConditionExpression=Key("estado").eq(estado),
                        ScanIndexForward=False,
                        ExclusiveStartKey=resp["LastEvaluatedKey"],
                    )
                    items.extend(resp.get("Items", []))
            else:
                from boto3.dynamodb.conditions import Attr
                resp = self.tbl_alertas.scan(
                    FilterExpression=Attr("tipo_registro").eq("META")
                )
                items = resp.get("Items", [])
                while "LastEvaluatedKey" in resp:
                    resp = self.tbl_alertas.scan(
                        FilterExpression=Attr("tipo_registro").eq("META"),
                        ExclusiveStartKey=resp["LastEvaluatedKey"],
                    )
                    items.extend(resp.get("Items", []))

            alertas: list[Alerta] = []
            for it in items:
                if it.get("tipo_registro") != "META":
                    continue
                try:
                    alertas.append(Alerta.model_validate(json.loads(it["payload"])))
                except Exception as e:
                    logger.warning(f"Error deserializando alerta {it.get('alerta_id')}: {e}")

            alertas.sort(key=lambda a: a.dinero_en_riesgo_cop, reverse=True)
            return alertas
        except ClientError as e:
            logger.error(f"Error listando alertas: {e}")
            raise

    def actualizar_alerta(self, alerta: Alerta, version_previa: int | None = None) -> bool:
        """Actualiza una alerta existente con bloqueo optimista opcional sobre `version_previa`."""
        if self.use_memory:
            actual = self._mem_alertas.get(alerta.alerta_id)
            if not actual:
                return False
            if version_previa is not None and actual.get("version") != version_previa:
                return False
            self._mem_alertas[alerta.alerta_id] = alerta.model_dump(mode="json")
            return True

        item = {
            "alerta_id": alerta.alerta_id,
            "tipo_registro": "META",
            "estado": alerta.estado.value,
            "dinero_en_riesgo_cop": Decimal(str(alerta.dinero_en_riesgo_cop)),
            "huella_causa": alerta.huella_causa,
            "severidad": alerta.severidad.value,
            "corte_creacion": alerta.corte_creacion.isoformat(),
            "creada_en": alerta.creada_en.isoformat(),
            "version": alerta.version,
            "payload": json.dumps(alerta.model_dump(mode="json")),
        }

        try:
            cond_expr = "attribute_exists(alerta_id)"
            expr_vals: dict[str, Any] = {}
            if version_previa is not None:
                cond_expr += " AND version = :v"
                expr_vals[":v"] = version_previa

            kwargs: dict[str, Any] = {"Item": item, "ConditionExpression": cond_expr}
            if expr_vals:
                kwargs["ExpressionAttributeValues"] = expr_vals

            self.tbl_alertas.put_item(**kwargs)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def guardar_propuesta(self, propuesta: Propuesta) -> bool:
        """Guarda la propuesta en centinela_alertas (tipo_registro = 'PROPUESTA') o en memoria."""
        if self.use_memory:
            self._mem_propuestas[propuesta.alerta_id] = propuesta.model_dump(mode="json")
            return True

        item = {
            "alerta_id": propuesta.alerta_id,
            "tipo_registro": "PROPUESTA",
            "generada_en": propuesta.generada_en.isoformat(),
            "modelo": propuesta.modelo,
            "payload": json.dumps(propuesta.model_dump(mode="json")),
        }
        try:
            self.tbl_alertas.put_item(Item=item)
            return True
        except ClientError as e:
            logger.error(f"Error guardando propuesta {propuesta.alerta_id}: {e}")
            raise

    def obtener_propuesta(self, alerta_id: str) -> Propuesta | None:
        """Recupera la propuesta asociada a una alerta."""
        if self.use_memory:
            raw = self._mem_propuestas.get(alerta_id)
            if not raw:
                return None
            return Propuesta.model_validate(raw)

        try:
            resp = self.tbl_alertas.get_item(
                Key={"alerta_id": alerta_id, "tipo_registro": "PROPUESTA"}
            )
            item = resp.get("Item")
            if not item:
                return None
            return Propuesta.model_validate(json.loads(item["payload"]))
        except ClientError as e:
            logger.error(f"Error obteniendo propuesta {alerta_id}: {e}")
            raise

    def obtener_propuestas(self, alerta_ids: list[str]) -> dict[str, Propuesta]:
        """Propuestas de varias alertas en pocas llamadas (BatchGetItem, de 100 en 100)."""
        if not alerta_ids:
            return {}
        if self.use_memory:
            return {i: Propuesta.model_validate(self._mem_propuestas[i]) for i in alerta_ids if i in self._mem_propuestas}
        salida: dict[str, Propuesta] = {}
        for inicio in range(0, len(alerta_ids), 100):
            lote = alerta_ids[inicio : inicio + 100]
            pendientes = {
                self.tbl_alertas.name: {
                    "Keys": [{"alerta_id": i, "tipo_registro": "PROPUESTA"} for i in lote]
                }
            }
            while pendientes:
                resp = self.dynamodb.batch_get_item(RequestItems=pendientes)
                for it in resp.get("Responses", {}).get(self.tbl_alertas.name, []):
                    salida[it["alerta_id"]] = Propuesta.model_validate(json.loads(it["payload"]))
                pendientes = resp.get("UnprocessedKeys") or {}
        return salida

    def guardar_resultado_ejecucion(self, resultado: ResultadoEjecucion) -> bool:
        """Guarda el resultado de ejecución (borradores sandbox)."""
        if self.use_memory:
            self._mem_resultados[resultado.alerta_id] = resultado.model_dump(mode="json")
            return True

        item = {
            "alerta_id": resultado.alerta_id,
            "tipo_registro": "EJECUCION",
            "ok": resultado.ok,
            "payload": json.dumps(resultado.model_dump(mode="json")),
        }
        try:
            self.tbl_alertas.put_item(Item=item)
            return True
        except ClientError as e:
            logger.error(f"Error guardando resultado ejecucion {resultado.alerta_id}: {e}")
            raise

    def obtener_resultado_ejecucion(self, alerta_id: str) -> ResultadoEjecucion | None:
        """Obtiene el resultado de ejecución para una alerta."""
        if self.use_memory:
            raw = self._mem_resultados.get(alerta_id)
            if not raw:
                return None
            return ResultadoEjecucion.model_validate(raw)

        try:
            resp = self.tbl_alertas.get_item(
                Key={"alerta_id": alerta_id, "tipo_registro": "EJECUCION"}
            )
            item = resp.get("Item")
            if not item:
                return None
            return ResultadoEjecucion.model_validate(json.loads(item["payload"]))
        except ClientError as e:
            logger.error(f"Error obteniendo resultado {alerta_id}: {e}")
            raise

    # -------------------------------------------------------------------------
    # centinela_bitacora
    # -------------------------------------------------------------------------
    def guardar_bitacora(self, entrada: EntradaBitacora) -> bool:
        """Sella una entrada en centinela_bitacora con PutItem inmutable."""
        if self.use_memory:
            cadena = self._mem_bitacora.setdefault(entrada.alerta_id, [])
            cadena.append(entrada)
            return True

        item = {
            "alerta_id": entrada.alerta_id,
            "seq": entrada.seq,
            "evento": entrada.evento.value,
            "actor": entrada.actor,
            "payload": json.dumps(entrada.payload),
            "ts": entrada.ts.isoformat(),
            "hash_prev": entrada.hash_prev,
            "hash": entrada.hash,
            "raw_json": json.dumps(entrada.model_dump(mode="json")),
        }

        try:
            self.tbl_bitacora.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(seq)",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def obtener_bitacora(self, alerta_id: str) -> list[EntradaBitacora]:
        """Obtiene la bitácora ordenada cronológicamente por secuencia."""
        if self.use_memory:
            cadena = self._mem_bitacora.get(alerta_id, [])
            return sorted(cadena, key=lambda x: x.seq)

        try:
            from boto3.dynamodb.conditions import Key
            resp = self.tbl_bitacora.query(
                KeyConditionExpression=Key("alerta_id").eq(alerta_id),
                ScanIndexForward=True,
            )
            items = resp.get("Items", [])
            entradas = [
                EntradaBitacora.model_validate(json.loads(it["raw_json"]))
                for it in items
            ]
            return entradas
        except ClientError as e:
            logger.error(f"Error consultando bitacora {alerta_id}: {e}")
            raise

    def sellar_evento(
        self,
        alerta_id: AlertaId,
        evento: Evento,
        actor: str,
        payload: dict,
    ) -> EntradaBitacora:
        """Crea y persiste la siguiente entrada encadenada en la bitácora."""
        historial = self.obtener_bitacora(alerta_id)
        previa = historial[-1] if historial else None
        entrada = EntradaBitacora.sellar(
            previa,
            alerta_id=alerta_id,
            evento=evento,
            actor=actor,
            payload=payload,
            ts=datetime.now(timezone.utc),
        )
        self.guardar_bitacora(entrada)
        return entrada

    # -------------------------------------------------------------------------
    # centinela_reloj
    # -------------------------------------------------------------------------
    def obtener_reloj(self) -> dict[str, Any]:
        """Obtiene el estado actual del reloj de simulación."""
        if self.use_memory:
            return {
                "corte": self._mem_reloj["corte"],
                "run_id": self._mem_reloj["run_id"],
                "actualizado_en": self._mem_reloj["actualizado_en"],
            }

        try:
            resp = self.tbl_reloj.get_item(
                Key={"reloj_pk": "RELOJ", "reloj_sk": "ACTUAL"}
            )
            item = resp.get("Item")
            if not item:
                # Inicializar si no existe
                now_str = datetime.now(timezone.utc).isoformat()
                init_item = {
                    "reloj_pk": "RELOJ",
                    "reloj_sk": "ACTUAL",
                    "corte": CORTE_INICIAL_LIMPIO.isoformat(),
                    "run_id": "bootstrap",
                    "actualizado_en": now_str,
                }
                self.tbl_reloj.put_item(Item=init_item)
                return {
                    "corte": CORTE_INICIAL_LIMPIO,
                    "run_id": "bootstrap",
                    "actualizado_en": now_str,
                }
            return {
                "corte": date.fromisoformat(item["corte"]),
                "run_id": item["run_id"],
                "actualizado_en": item["actualizado_en"],
            }
        except ClientError as e:
            logger.error(f"Error consultando reloj: {e}")
            raise

    def actualizar_reloj(self, nuevo_corte: date, run_id: str) -> dict[str, Any]:
        """Actualiza la fecha de corte y run_id del reloj."""
        now_str = datetime.now(timezone.utc).isoformat()
        if self.use_memory:
            self._mem_reloj = {
                "corte": nuevo_corte,
                "run_id": run_id,
                "actualizado_en": now_str,
            }
            return self._mem_reloj

        item = {
            "reloj_pk": "RELOJ",
            "reloj_sk": "ACTUAL",
            "corte": nuevo_corte.isoformat(),
            "run_id": run_id,
            "actualizado_en": now_str,
        }
        self.tbl_reloj.put_item(Item=item)
        return {
            "corte": nuevo_corte,
            "run_id": run_id,
            "actualizado_en": now_str,
        }

    def reiniciar_reloj(self) -> dict[str, Any]:
        """Restablece el reloj al corte inicial limpio."""
        return self.actualizar_reloj(CORTE_INICIAL_LIMPIO, "reiniciado")

    def guardar_traza(self, traza: TrazaLLM) -> bool:
        """Guarda una traza LLM en centinela_trazas con TTL 30 días o en memoria."""
        clave_pk = traza.alerta_id or f"CHAT#{traza.run_id}"
        if self.use_memory:
            lista = self._mem_trazas.setdefault(clave_pk, [])
            lista.append(traza.model_dump(mode="json"))
            return True

        ts_str = traza.ts.isoformat()
        ts_tipo = f"{ts_str}#{traza.agente}"
        ttl_val = int(traza.ts.timestamp()) + (30 * 86400)

        item = {
            "alerta_id": clave_pk,
            "ts_tipo": ts_tipo,
            "run_id": traza.run_id,
            "agente": traza.agente,
            "modelo": traza.modelo,
            "tokens_in": traza.tokens_in,
            "tokens_out": traza.tokens_out,
            "tokens_cache_lectura": traza.tokens_cache_lectura,
            "latencia_ms": traza.latencia_ms,
            "costo_usd": Decimal(str(traza.costo_usd)),
            "guardrail_intervino": traza.guardrail_intervino,
            "consulta_ids": traza.consulta_ids,
            "reintentos": traza.reintentos,
            "error": traza.error or "",
            "ttl": ttl_val,
            "payload": json.dumps(traza.model_dump(mode="json")),
        }
        try:
            self.tbl_trazas.put_item(Item=item)
            return True
        except ClientError as e:
            logger.error(f"Error guardando traza para {clave_pk}: {e}")
            raise

    def obtener_trazas(self, alerta_id: str) -> list[TrazaLLM]:
        """Obtiene las trazas LLM asociadas a una alerta."""
        if self.use_memory:
            raw_list = self._mem_trazas.get(alerta_id, [])
            return [TrazaLLM.model_validate(r) for r in raw_list]

        try:
            from boto3.dynamodb.conditions import Key
            resp = self.tbl_trazas.query(
                KeyConditionExpression=Key("alerta_id").eq(alerta_id)
            )
            items = resp.get("Items", [])
            trazas = [
                TrazaLLM.model_validate(json.loads(it["payload"]))
                for it in items
                if "payload" in it
            ]
            return trazas
        except ClientError as e:
            logger.error(f"Error obteniendo trazas {alerta_id}: {e}")
            raise

    # -------------------------------------------------------------------------
    # centinela_config (configuración y feedback de rechazos)
    # -------------------------------------------------------------------------
    def guardar_feedback(self, alerta_id: str, motivo: str, actor: str, **contexto: Any) -> bool:
        """Guarda el motivo de rechazo. `contexto` (huella, tipos de acción, entidades) alimenta el aprendizaje."""
        now_str = datetime.now(timezone.utc).isoformat()
        record = {
            "alerta_id": alerta_id,
            "motivo": motivo,
            "actor": actor,
            "ts": now_str,
            **contexto,
        }
        if self.use_memory:
            self._mem_feedback.append(record)
            return True
        item = {"clave": f"FEEDBACK#{now_str}#{alerta_id}", **json.loads(json.dumps(record))}
        self.tbl_config.put_item(Item=item)
        return True

    def obtener_feedback(self, huella: str | None = None, familia: str | None = None, limite: int = 20) -> list[dict]:
        """Rechazos recientes (más nuevos primero), opcionalmente de una misma causa (`huella`) o familia de causa."""
        if self.use_memory:
            items = list(self._mem_feedback)
        else:
            from boto3.dynamodb.conditions import Attr

            filtro = Attr("clave").begins_with("FEEDBACK#")
            resp = self.tbl_config.scan(FilterExpression=filtro)
            items = resp.get("Items", [])
            while "LastEvaluatedKey" in resp:
                resp = self.tbl_config.scan(FilterExpression=filtro, ExclusiveStartKey=resp["LastEvaluatedKey"])
                items.extend(resp.get("Items", []))
        if huella:
            items = [it for it in items if it.get("huella_causa") == huella]
        if familia:
            items = [it for it in items if it.get("familia") == familia]
        items.sort(key=lambda it: it.get("ts", ""), reverse=True)
        return items[:limite]

    def obtener_config(self, clave: str) -> dict | None:
        """Lee un documento de configuración (p. ej. `umbrales`)."""
        if self.use_memory:
            return self._mem_config.get(clave)
        resp = self.tbl_config.get_item(Key={"clave": f"CONFIG#{clave}"})
        item = resp.get("Item")
        return json.loads(item["valor"]) if item else None

    def guardar_config(self, clave: str, valor: dict, actor: str) -> None:
        """Guarda un documento de configuración con fecha y autor de la actualización."""
        if self.use_memory:
            self._mem_config[clave] = valor
            return
        self.tbl_config.put_item(
            Item={
                "clave": f"CONFIG#{clave}",
                "valor": json.dumps(valor),
                "actualizado_en": datetime.now(timezone.utc).isoformat(),
                "actualizado_por": actor,
            }
        )

    # -------------------------------------------------------------------------
    # Consultas registradas (centinela_trazas, PK = QUERY#<consulta_id>)
    # -------------------------------------------------------------------------
    def guardar_consulta(self, consulta: ConsultaRegistrada) -> None:
        """Persiste una consulta registrada (idempotente: el id es determinista)."""
        if self.use_memory:
            self._mem_consultas[consulta.consulta_id] = consulta.model_dump(mode="json")
            return
        ttl = int(datetime.now(timezone.utc).timestamp()) + 30 * 86400
        self.tbl_trazas.put_item(
            Item={
                "alerta_id": f"QUERY#{consulta.consulta_id}",
                "ts_tipo": "v1",
                "ttl": ttl,
                "payload": consulta.model_dump_json(),
            }
        )

    def obtener_consulta(self, consulta_id: str) -> ConsultaRegistrada | None:
        if self.use_memory:
            raw = self._mem_consultas.get(consulta_id)
            return ConsultaRegistrada.model_validate(raw) if raw else None
        resp = self.tbl_trazas.get_item(Key={"alerta_id": f"QUERY#{consulta_id}", "ts_tipo": "v1"})
        item = resp.get("Item")
        return ConsultaRegistrada.model_validate_json(item["payload"]) if item else None

    # -------------------------------------------------------------------------
    # Alertas: una por causa (huella), sincronización con el Vigía y reinicio de demo
    # -------------------------------------------------------------------------
    def alertas_por_huella(self) -> dict[str, Alerta]:
        """Alertas persistidas indexadas por `huella_causa` (una por causa)."""
        return {a.huella_causa: a for a in self.listar_alertas()}

    def sincronizar_alertas(self, vivas: list[Alerta], crear: bool = True) -> list[Alerta]:
        """Une las alertas vivas del Vigía con las persistidas, por `huella_causa`.

        - Si la causa ya tiene alerta persistida: conserva id, estado, versión, paso y fecha de creación,
          y toma hallazgos, severidad y dinero en riesgo del corte actual.
        - Si no existe y `crear`: la persiste (con sus consultas y la entrada de bitácora de creación).
        - Si no existe y no `crear`: la devuelve sin persistir.
        Las causas persistidas que ya no se detectan no se devuelven.
        """
        persistidas = self.alertas_por_huella()
        resultado: list[Alerta] = []
        nuevas: list[Alerta] = []
        for viva in vivas:
            previa = persistidas.get(viva.huella_causa)
            if previa is None:
                nuevas.append(viva)
                resultado.append(viva)
            else:
                resultado.append(
                    previa.model_copy(
                        update={
                            "hallazgos": viva.hallazgos,
                            "severidad": viva.severidad,
                            "dinero_en_riesgo_cop": viva.dinero_en_riesgo_cop,
                        }
                    )
                )
        if crear and nuevas:
            self.persistir_alertas_nuevas(nuevas)
        resultado.sort(key=lambda a: a.dinero_en_riesgo_cop, reverse=True)
        return resultado

    def persistir_alertas_nuevas(self, alertas: list[Alerta]) -> int:
        """Persiste alertas nuevas con sus consultas y la entrada `alerta_creada` de la bitácora."""
        from services.registro_consultas import consulta_en_cache

        consultas_vistas: set[str] = set()
        for a in alertas:
            for h in a.hallazgos:
                for cid in h.consulta_ids:
                    if cid in consultas_vistas:
                        continue
                    consultas_vistas.add(cid)
                    c = consulta_en_cache(cid)
                    if c is not None:
                        self.guardar_consulta(c)

        def _crear(a: Alerta) -> int:
            if not self.guardar_alerta(a):
                return 0
            self.sellar_evento(
                alerta_id=a.alerta_id,
                evento=Evento.ALERTA_CREADA,
                actor="vigia",
                payload={
                    "huella_causa": a.huella_causa,
                    "severidad": a.severidad.value,
                    "dinero_en_riesgo_cop": float(a.dinero_en_riesgo_cop),
                    "corte_creacion": a.corte_creacion.isoformat(),
                    "num_hallazgos": len(a.hallazgos),
                },
            )
            return 1

        if self.use_memory:
            return sum(_crear(a) for a in alertas)
        with ThreadPoolExecutor(max_workers=12) as pool:
            return sum(pool.map(_crear, alertas))

    def borrar_estado_demo(self) -> dict[str, int]:
        """Reinicio de demo: borra alertas, propuestas, ejecuciones, trazas y rechazos. La bitácora se conserva."""
        borrados = {"alertas": 0, "trazas": 0, "feedback": 0}
        if self.use_memory:
            borrados["alertas"] = len(self._mem_alertas)
            self._mem_alertas.clear()
            self._mem_propuestas.clear()
            self._mem_resultados.clear()
            borrados["trazas"] = len(self._mem_trazas) + len(self._mem_consultas)
            self._mem_trazas.clear()
            self._mem_consultas.clear()
            borrados["feedback"] = len(self._mem_feedback)
            self._mem_feedback.clear()
            return borrados

        from boto3.dynamodb.conditions import Attr

        def _vaciar(tabla, claves: tuple[str, ...], filtro=None) -> int:
            kwargs: dict[str, Any] = {
                "ProjectionExpression": ", ".join(f"#k{i}" for i in range(len(claves))),
                "ExpressionAttributeNames": {f"#k{i}": k for i, k in enumerate(claves)},
            }
            if filtro is not None:
                kwargs["FilterExpression"] = filtro
            total = 0
            resp = tabla.scan(**kwargs)
            while True:
                with tabla.batch_writer() as lote:
                    for it in resp.get("Items", []):
                        lote.delete_item(Key={k: it[k] for k in claves})
                        total += 1
                if "LastEvaluatedKey" not in resp:
                    break
                resp = tabla.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
            return total

        borrados["alertas"] = _vaciar(self.tbl_alertas, ("alerta_id", "tipo_registro"))
        borrados["trazas"] = _vaciar(self.tbl_trazas, ("alerta_id", "ts_tipo"))
        borrados["feedback"] = _vaciar(self.tbl_config, ("clave",), Attr("clave").begins_with("FEEDBACK#"))
        return borrados

    # -------------------------------------------------------------------------
    # Bitácora general (auditoría de toda la operación)
    # -------------------------------------------------------------------------
    def listar_bitacora(
        self,
        limite: int = 50,
        actor: str | None = None,
        evento: str | None = None,
    ) -> list[EntradaBitacora]:
        """Entradas de bitácora de todas las alertas, más recientes primero, con filtros opcionales."""
        if self.use_memory:
            entradas = [e for cadena in self._mem_bitacora.values() for e in cadena]
        else:
            resp = self.tbl_bitacora.scan()
            items = resp.get("Items", [])
            while "LastEvaluatedKey" in resp:
                resp = self.tbl_bitacora.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
                items.extend(resp.get("Items", []))
            entradas = [EntradaBitacora.model_validate(json.loads(it["raw_json"])) for it in items]
        if actor:
            entradas = [e for e in entradas if e.actor == actor]
        if evento:
            entradas = [e for e in entradas if e.evento.value == evento]
        entradas.sort(key=lambda e: e.ts, reverse=True)
        return entradas[:limite]


# Instancia por defecto del servicio
persistencia_service = PersistenciaService()

