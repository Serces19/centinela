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

from contracts.alertas import Alerta
from contracts.base import AlertaId, EstadoAlerta
from contracts.bitacora import EntradaBitacora, Evento
from contracts.configuracion import CORTE_INICIAL_LIMPIO

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
            else:
                resp = self.tbl_alertas.scan()

            items = resp.get("Items", [])
            alertas = [Alerta.model_validate(json.loads(it["payload"])) for it in items]
            alertas.sort(key=lambda a: a.dinero_en_riesgo_cop, reverse=True)
            return alertas
        except ClientError as e:
            logger.error(f"Error listando alertas: {e}")
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


# Instancia por defecto del servicio
persistencia_service = PersistenciaService()

