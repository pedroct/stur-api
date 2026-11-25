from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from stur_api.main import criar_app
from stur_api.servicos.consultas import ServicoConsulta
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


def test_saude_stur_com_erro_do_httpx_nao_traduzido(
    cliente_http: TestClient, agi: AgiFalsa
) -> None:
    # o cliente só traduz tempo esgotado e erro de transporte; o resto do httpx também é
    # "sem resposta", e não um 500 (R18)
    agi.login.side_effect = httpx.DecodingError("x")
    r = cliente_http.get("/api/v1/saude/stur")
    assert r.status_code == 200
    assert r.json() == {"apiStur": "sem_resposta"}


def test_ciclo_de_vida_monta_o_servico_real_a_partir_do_ambiente(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # sem `.env` por perto
    monkeypatch.setenv("STUR_API_URL", "https://agi.exemplo.invalid")
    monkeypatch.setenv("STUR_API_USUARIO", "usuario-de-teste")
    monkeypatch.setenv("STUR_API_SENHA", "senha-de-teste")
    app = criar_app()
    with TestClient(app) as http:
        assert isinstance(app.state.servico, ServicoConsulta)
        assert http.get("/api/v1/saude").status_code == 200
