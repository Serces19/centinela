"""Centinela Tools package."""

from .consultas import ValidadorConsultaError, consultar_vista
from .impacto import calcular_impacto

__all__ = [
    "consultar_vista",
    "ValidadorConsultaError",
    "calcular_impacto",
]
