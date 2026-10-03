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
        self._mem_feedback: dict[str, list[dict]] = {}
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

    def persistir_alertas_vigia(self, alertas: list[Alerta]) -> tuple[int, int]:
        """Persiste una lista de alertas deterministas generadas por el Vigía.

        - Guarda cada alerta con PutItem condicional.
        - Si la alerta es nueva, sella EntradaBitacora con Evento.ALERTA_CREADA.
        - Si ya existía, omite sin modificar.
        Retorna (creadas, omitidas_duplicadas).
        """
        creadas = 0
        omitidas = 0
        for a in alertas:
            es_nueva = self.guardar_alerta(a)
            if es_nueva:
                creadas += 1
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
            else:
                omitidas += 1
        return creadas, omitidas


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
    # centinela_config (Feedback y Aprendizaje)
    # -------------------------------------------------------------------------
    def guardar_feedback(self, alerta_id: str, motivo: str, actor: str) -> bool:
        """Guarda el motivo de rechazo en la configuración de feedback (base de aprendizaje)."""
        now_str = datetime.now(timezone.utc).isoformat()
        record = {
            "alerta_id": alerta_id,
            "motivo": motivo,
            "actor": actor,
            "ts": now_str,
        }
        if self.use_memory:
            self._mem_feedback.setdefault(alerta_id, []).append(record)
            return True

        item = {
            "config_pk": "FEEDBACK",
            "config_sk": f"{alerta_id}#{now_str}",
            "alerta_id": alerta_id,
            "motivo": motivo,
            "actor": actor,
            "ts": now_str,
        }
        try:
            self.tbl_config.put_item(Item=item)
            return True
        except Exception as e:
            logger.warning(f"Error guardando feedback {alerta_id} en DynamoDB ({e}). Guardando en memoria.")
            self._mem_feedback.setdefault(alerta_id, []).append(record)
            return True

    def obtener_feedback(self, alerta_id: str | None = None) -> list[dict]:
        """Recupera los motivos de rechazo guardados para análisis o aprendizaje."""
        if self.use_memory:
            if alerta_id:
                return self._mem_feedback.get(alerta_id, [])
            todos: list[dict] = []
            for fbs in self._mem_feedback.values():
                todos.extend(fbs)
            return todos

        try:
            from boto3.dynamodb.conditions import Key
            resp = self.tbl_config.query(
                KeyConditionExpression=Key("config_pk").eq("FEEDBACK")
            )
            items = resp.get("Items", [])
            if alerta_id:
                return [it for it in items if it.get("alerta_id") == alerta_id]
            return items
        except Exception as e:
            logger.warning(f"Error consultando feedback en DynamoDB ({e}). Retornando de memoria.")
            if alerta_id:
                return self._mem_feedback.get(alerta_id, [])
            todos = []
            for fbs in self._mem_feedback.values():
                todos.extend(fbs)
            return todos


# Instancia por defecto del servicio
persistencia_service = PersistenciaService()

