from fastapi.testclient import TestClient

from stur_api.main import criar_app


def test_saude_responde_ok() -> None:
    resposta = TestClient(criar_app()).get("/api/v1/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"aplicacao": "ok"}
