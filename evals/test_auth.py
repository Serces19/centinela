"""R1: la API exige x-api-key salvo en /health."""
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture()
def cliente_con_auth(monkeypatch):
    monkeypatch.setenv("CENTINELA_AUTH_DISABLED", "false")
    monkeypatch.setenv("CENTINELA_API_KEY", "clave-de-prueba")
    with TestClient(app) as c:
        yield c


def test_health_es_publico(cliente_con_auth):
    assert cliente_con_auth.get("/health").status_code == 200


@pytest.mark.parametrize(
    "metodo,ruta",
    [("get", "/alertas"), ("get", "/simulacion/corte"), ("post", "/simulacion/reiniciar"), ("post", "/chat")],
)
def test_sin_clave_devuelve_401(cliente_con_auth, metodo, ruta):
    resp = getattr(cliente_con_auth, metodo)(ruta)
    assert resp.status_code == 401
    assert resp.json()["codigo"] == "no_autorizado"


def test_clave_erronea_devuelve_401(cliente_con_auth):
    assert cliente_con_auth.get("/alertas", headers={"x-api-key": "otra"}).status_code == 401


def test_clave_correcta_pasa(cliente_con_auth):
    resp = cliente_con_auth.get("/simulacion/corte", headers={"x-api-key": "clave-de-prueba"})
    assert resp.status_code == 200


def test_sin_clave_configurada_falla_cerrada(monkeypatch):
    monkeypatch.setenv("CENTINELA_AUTH_DISABLED", "false")
    monkeypatch.delenv("CENTINELA_API_KEY", raising=False)
    monkeypatch.setenv("CENTINELA_API_KEY_PARAM", "/centinela/no_existe_test")
    with TestClient(app) as c:
        assert c.get("/simulacion/corte", headers={"x-api-key": "x"}).status_code == 401
