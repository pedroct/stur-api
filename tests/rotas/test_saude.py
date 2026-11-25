import httpx
from fastapi.testclient import TestClient

from stur_api.main import criar_app
from tests.agi_falsa import AgiFalsa


def test_saude_responde_ok() -> None:
    resposta = TestClient(criar_app()).get("/api/v1/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"aplicacao": "ok"}


def test_saude_stur(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # login 401 → "acesso_recusado"; saude continua {"aplicacao": "ok"}
    agi.login.return_value = httpx.Response(401)
    r = cliente_http.get("/api/v1/saude/stur")
    assert r.status_code == 200
    assert r.json() == {"apiStur": "acesso_recusado"}
    assert cliente_http.get("/api/v1/saude").json() == {"aplicacao": "ok"}


def test_saude_stur_ok(cliente_http: TestClient, agi: AgiFalsa) -> None:
    r = cliente_http.get("/api/v1/saude/stur")
    assert r.status_code == 200
    assert r.json() == {"apiStur": "ok"}
    assert agi.login.call_count == 1


def test_saude_stur_sem_resposta(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.login.side_effect = httpx.ConnectError("x")
    r = cliente_http.get("/api/v1/saude/stur")
    assert r.status_code == 200
    assert r.json() == {"apiStur": "sem_resposta"}
