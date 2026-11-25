"""Logs de requisição: uma linha por pedido, sem dado pessoal (Review Focus 5, R9, R18b)."""

import logging
import traceback
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from stur_api.main import criar_app
from stur_api.registro import configurar_registro
from stur_api.servicos.consultas import ServicoConsulta
from tests import fabrica
from tests.agi_falsa import AgiFalsa

ROTA_DA_VENDA = "rota=/api/v1/reservas/{numero}/vendas/{idreserva}"


def _linhas_de_requisicao(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "api.requisicao"]


def test_log_nao_tem_filtro_nem_corpo(
    cliente_http: TestClient, agi: AgiFalsa, caplog: pytest.LogCaptureFixture
) -> None:
    # `cliente_http` vem de `criar_app`, que chama `configurar_registro`: o teste vê os logs
    # como a aplicação os configura. Com tudo em DEBUG na raiz, o INFO do httpx (que grava a
    # URL da AGI) apareceria aqui se `configurar_registro` não o silenciasse.
    caplog.set_level(logging.DEBUG)
    agi.vendas = [
        fabrica.venda(
            nomecliente="MARIA DA SILVA",
            detalheItem=[fabrica.servico(nomePax="MARIA DA SILVA")],
        )
    ]
    cliente_http.get(
        "/api/v1/vendas",
        params={"reserva": "90000001", "de": "2026-11-01", "ate": "2026-11-17", "cliente": "maria"},
    )
    cliente_http.get("/api/v1/reservas/90000001/vendas/1001")
    assert "MARIA" not in caplog.text.upper() and "maria" not in caplog.text
    assert ROTA_DA_VENDA in caplog.text and "idreserva=1001" in caplog.text
    assert "agi.exemplo.invalid" not in caplog.text  # a URL da AGI nunca vai ao log
    assert "senha-de-teste" not in caplog.text


def test_linha_tem_metodo_rota_numero_status_e_duracao(
    cliente_http: TestClient, agi: AgiFalsa, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    cliente_http.get("/api/v1/reservas/90000001/vendas/1001")
    (linha,) = _linhas_de_requisicao(caplog)
    assert "metodo=GET" in linha
    assert ROTA_DA_VENDA in linha
    assert "numero=90000001" in linha and "idreserva=1001" in linha
    assert "status=200" in linha
    assert "duracao_ms=" in linha


def test_rota_sem_parametros_nao_leva_numero_nem_query(
    cliente_http: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    cliente_http.get("/api/v1/parametros", params={"cliente": "maria"})
    (linha,) = _linhas_de_requisicao(caplog)
    assert "rota=/api/v1/parametros " in linha
    assert "numero=" not in linha and "idreserva=" not in linha
    assert "maria" not in linha and "cliente" not in linha


def test_numero_que_nao_e_digito_nao_vai_ao_log(
    cliente_http: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    r = cliente_http.get("/api/v1/reservas/MARIA")
    assert r.status_code == 422
    (linha,) = _linhas_de_requisicao(caplog)
    assert "MARIA" not in linha.upper()
    assert "status=422" in linha


def test_rota_inexistente_loga_marcador_e_nao_o_caminho(
    cliente_http: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    r = cliente_http.get("/api/v1/clientes/MARIA-DA-SILVA?x=maria")
    assert r.status_code == 404
    (linha,) = _linhas_de_requisicao(caplog)
    assert "rota=- " in linha and "status=404" in linha and "duracao_ms=" in linha
    assert "MARIA" not in caplog.text.upper() and "clientes" not in caplog.text


def test_excecao_no_handler_loga_status_500_e_nao_engole(
    servico: ServicoConsulta,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Prova só a linha do NOSSO middleware (status 500, rota, classe) e que a exceção sobe.

    O que o uvicorn escreve ao receber essa exceção NÃO é coberto aqui: o TestClient não é o
    uvicorn. Isso é o `test_traceback_do_uvicorn_...` abaixo.
    """
    app = criar_app(servico)

    @app.get("/api/v1/explode/{numero}")
    async def explode(numero: int) -> None:
        raise ValueError("MARIA DA SILVA")

    caplog.set_level(logging.INFO)
    with TestClient(app, raise_server_exceptions=False) as http:
        r = http.get("/api/v1/explode/90000001")
    assert r.status_code == 500
    assert r.json()["codigo"] == "erro_interno"
    (linha,) = _linhas_de_requisicao(caplog)
    assert "status=500" in linha and "numero=90000001" in linha
    assert "rota=/api/v1/explode/{numero}" in linha
    assert "erro=ValueError" in linha
    assert "MARIA" not in linha.upper()  # a linha do middleware nunca leva a mensagem

    # a exceção continua subindo: com raise_server_exceptions o cliente de teste a vê
    with TestClient(app) as http, pytest.raises(ValueError):
        http.get("/api/v1/explode/90000001")


def test_rota_nao_encontrada_no_envelope(cliente_http: TestClient) -> None:
    r = cliente_http.get("/api/v1/nao-existe")
    assert r.status_code == 404
    assert r.json() == {
        "codigo": "rota_inexistente",
        "mensagem": "Esta rota não existe nesta API.",
        "detalhe": None,
    }


def test_metodo_nao_permitido_no_envelope(cliente_http: TestClient) -> None:
    r = cliente_http.post("/api/v1/saude")
    assert r.status_code == 405
    assert r.json() == {
        "codigo": "metodo_nao_permitido",
        "mensagem": "Este método não é permitido nesta rota.",
        "detalhe": None,
    }
    assert "GET" in r.headers["allow"]


def test_outro_status_http_vira_erro_http(servico: ServicoConsulta) -> None:
    from fastapi import HTTPException

    app = criar_app(servico)

    @app.get("/api/v1/proibido")
    async def proibido() -> None:
        raise HTTPException(status_code=403, detail="MARIA DA SILVA")

    r = TestClient(app).get("/api/v1/proibido")
    assert r.status_code == 403
    assert r.json()["codigo"] == "erro_http"
    assert "MARIA" not in r.text  # nunca ecoa o `detail`


def test_configurar_registro_silencia_httpx_e_nao_mexe_no_access_log() -> None:
    acesso = logging.getLogger("uvicorn.access")
    antes = (acesso.level, acesso.disabled, list(acesso.handlers), acesso.propagate)
    configurar_registro()
    configurar_registro()  # idempotente
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert (acesso.level, acesso.disabled, list(acesso.handlers), acesso.propagate) == antes
    marcados = [h for h in logging.getLogger().handlers if getattr(h, "_stur_api", False)]
    assert len(marcados) == 1
    for destino in (marcados[0], logging.getLogger("uvicorn.error")):
        assert len([f for f in destino.filters if getattr(f, "_stur_api", False)]) == 1


def test_formato_chave_valor(capsys: pytest.CaptureFixture[str]) -> None:
    configurar_registro()
    logging.getLogger("api.requisicao").info("metodo=GET rota=/x status=200")
    err = capsys.readouterr().err
    assert "nivel=INFO" in err and "logger=api.requisicao" in err
    assert "metodo=GET rota=/x status=200" in err


# --- exceção não tratada: o uvicorn a registra com traceback (fix round 1) ---


class _Dados(BaseModel):
    numero: int
    passageiros: list[str]


def _formatado_pelo_nosso_handler(registro: logging.LogRecord) -> str:
    (nosso,) = [h for h in logging.getLogger().handlers if getattr(h, "_stur_api", False)]
    return nosso.format(registro)


def test_traceback_do_uvicorn_nao_leva_mensagem_da_excecao(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """Emite exatamente como o uvicorn faz (h11_impl: `logger.error(..., exc_info=exc)`)."""
    configurar_registro()
    caplog.set_level(logging.DEBUG)
    logging.getLogger("uvicorn.error").error(
        "Exception in ASGI application\n", exc_info=ValueError("MARIA DA SILVA")
    )
    (registro,) = [r for r in caplog.records if r.name == "uvicorn.error"]
    assert registro.getMessage() == "excecao_nao_tratada erro=ValueError"
    assert registro.exc_info is None and registro.exc_text is None
    assert "MARIA" not in caplog.text.upper()
    assert "MARIA" not in _formatado_pelo_nosso_handler(registro).upper()
    assert "Traceback" not in caplog.text


def test_validation_error_do_pydantic_nao_vaza_input_value(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    configurar_registro()
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ValidationError) as capturado:
        _Dados.model_validate({"passageiros": ["JOAO PASSAGEIRO"]})  # falta `numero`
    assert "JOAO PASSAGEIRO" in str(capturado.value)  # sanidade: o erro original TEM o nome
    erro = capturado.value
    logging.getLogger("uvicorn.error").error(
        "Exception in ASGI application\n", exc_info=(type(erro), erro, erro.__traceback__)
    )
    # o que vem de outro logger (asyncio, por exemplo) chega à raiz: o handler nosso filtra
    logging.getLogger("asyncio").error("Task exception was never retrieved", exc_info=erro)
    assert "JOAO" not in caplog.text.upper()
    saida = capsys.readouterr().err
    assert "JOAO" not in saida.upper() and "input_value" not in saida
    assert "excecao_nao_tratada erro=ValidationError" in saida
    assert "excecao_nao_tratada erro=ValidationError" in caplog.text


def test_registros_sem_excecao_ficam_como_estao(caplog: pytest.LogCaptureFixture) -> None:
    configurar_registro()
    caplog.set_level(logging.DEBUG)
    logging.getLogger("qualquer").warning("busca %s falhou erro=%s", "1005", "Classe")
    logging.getLogger("uvicorn.error").info("Application startup complete.")
    mensagens = [r.getMessage() for r in caplog.records]
    assert mensagens == ["busca 1005 falhou erro=Classe", "Application startup complete."]


# --- lifespan: configuração inválida sem valores (R18b) ---

SEGREDOS = {
    "STUR_API_USUARIO": "usuario-secreto-xyz",
    "STUR_API_SENHA": "senha-secreta-xyz",
    "AGI_ITENS_POR_PAGINA": "valor-secreto-xyz",
}


def test_configuracao_invalida_sobe_sem_valores(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # sem `.env` por perto
    monkeypatch.delenv("STUR_API_URL", raising=False)
    for nome, valor in SEGREDOS.items():
        monkeypatch.setenv(nome, valor)
    app: FastAPI = criar_app()
    with pytest.raises(RuntimeError) as capturado, TestClient(app):
        pass
    erro = capturado.value
    texto = "\n".join(
        [str(erro), repr(erro), *traceback.format_exception(type(erro), erro, erro.__traceback__)]
    )
    assert str(erro).startswith("Configuração inválida: ")
    assert "stur_api_url: missing" in str(erro)
    assert "agi_itens_por_pagina: int_parsing" in str(erro)
    for segredo in SEGREDOS.values():
        assert segredo not in texto
    assert erro.__cause__ is None and erro.__suppress_context__


def test_httpx_nao_loga_a_url_da_agi(
    cliente_http: TestClient, agi: AgiFalsa, caplog: pytest.LogCaptureFixture
) -> None:
    """Sentinela: sem o silenciamento, o httpx gravaria `HTTP Request: POST <url> ...`."""
    caplog.set_level(logging.DEBUG)
    cliente_http.get("/api/v1/saude/stur")
    assert agi.login.call_count == 1
    assert not [r for r in caplog.records if r.name in ("httpx", "httpcore")]
