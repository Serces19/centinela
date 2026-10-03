# backend/contracts/bitacora.py
import hashlib
import json
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from .base import AlertaId, CERO_HASH, Contrato, Hash256, SCHEMA_VERSION


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
        return cls(
            alerta_id=alerta_id,
            seq=seq,
            evento=evento,
            actor=actor,
            payload=payload,
            ts=ts,
            hash_prev=hash_prev,
            hash=h,
        )


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
