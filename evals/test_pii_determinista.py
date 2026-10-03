"""evals/test_pii_determinista.py

Pruebas de la capa determinista de PII (PII segregation / desidentificacion estricta).
Verifica que:
1. El Vigia y sus Hallazgos solo contengan IDs tecnicos (V03, C0496, PR08) y nunca nombres propios.
2. Ningun prompt o hallazgo generado contenga nombres extraidos de vendedores.csv.
3. La resolucion de nombres sea una funcion determinista separada (resolver_nombres)
   destinada exclusivamente a la capa de presentacion (UI).
"""

from datetime import date
from pathlib import Path
import csv
import pytest

from agents.vigia import generar_alertas
from services.resolucion import resolver_nombres


@pytest.fixture(scope="module")
def nombres_vendedores():
    """Extrae la lista de nombres y apellidos de vendedores.csv."""
    csv_path = Path(__file__).resolve().parent.parent / "Kit_Equipos" / "datos" / "csv" / "vendedores.csv"
    assert csv_path.exists(), f"No existe {csv_path}"

    nombres = set()
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nombre = row.get("nombre", "").strip()
            if nombre:
                nombres.add(nombre)
                # Tambien agregar nombres o apellidos individuales significativos (>3 letras)
                for parte in nombre.split():
                    if len(parte) > 3:
                        nombres.add(parte)
    return nombres


def test_hallazgos_sin_nombres_vendedores(nombres_vendedores):
    """Verifica que ningun Hallazgo ni Alerta contenga nombres propios de vendedores."""
    cortes = [date(2026, 9, 30), date(2026, 8, 15)]

    for corte in cortes:
        alertas = generar_alertas(corte=corte)
        assert len(alertas) > 0

        for alerta in alertas:
            # Inspeccionar la huella, el ID y las entidades
            texto_alerta = f"{alerta.alerta_id} {alerta.huella_causa} {alerta.severidad.value}"
            for nombre in nombres_vendedores:
                assert nombre.lower() not in texto_alerta.lower(), (
                    f"PII filtrado en Alerta: '{nombre}' encontrado en '{texto_alerta}'"
                )

            for hallazgo in alerta.hallazgos:
                texto_hallazgo = (
                    f"{hallazgo.hallazgo_id} {hallazgo.huella_causa} {hallazgo.regla} "
                    f"{[e.id for e in hallazgo.entidades]}"
                )
                for nombre in nombres_vendedores:
                    assert nombre.lower() not in texto_hallazgo.lower(), (
                        f"PII filtrado en Hallazgo: '{nombre}' encontrado en '{texto_hallazgo}'"
                    )

                # Verificar que las entidades solo tengan IDs formales
                for ent in hallazgo.entidades:
                    assert ent.id.startswith(("V", "C", "PR", "P", "BOD")), f"ID no conforme: {ent.id}"


def test_servicio_resolucion_nombres_aislado():
    """Verifica que resolver_nombres traduzca IDs a nombres solo para la UI bajo demanda."""
    ids = ["V03", "PR08"]
    res = resolver_nombres(ids)

    assert "V03" in res
    assert isinstance(res["V03"], str)
    assert len(res["V03"]) > 3

    assert "PR08" in res
    assert isinstance(res["PR08"], str)
