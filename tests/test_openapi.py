"""Contrato exportado: o `openapi.json` versionado é a fonte dos tipos do frontend (plano 2)."""

import json
from pathlib import Path
from typing import Any

import pytest

from stur_api.main import criar_app
from stur_api.openapi_export import main, serializar

RAIZ = Path(__file__).resolve().parent.parent
SEIS_ROTAS = {
    "/api/v1/vendas": "get",
    "/api/v1/reservas/{numero}": "get",
    "/api/v1/reservas/{numero}/vendas/{idreserva}": "get",
    "/api/v1/reservas/{numero}/vendas/{idreserva}/dado-cru": "get",
    "/api/v1/parametros": "get",
    "/api/v1/saude": "get",
    "/api/v1/saude/stur": "get",
}
OPERATION_IDS = {
    ("/api/v1/vendas", "get"): "consultar_vendas",
    ("/api/v1/reservas/{numero}", "get"): "abrir_reserva",
    ("/api/v1/reservas/{numero}/vendas/{idreserva}", "get"): "abrir_venda",
    ("/api/v1/reservas/{numero}/vendas/{idreserva}/dado-cru", "get"): "dado_cru_da_venda",
    ("/api/v1/parametros", "get"): "parametros",
    ("/api/v1/saude", "get"): "saude",
    ("/api/v1/saude/stur", "get"): "saude_stur",
}


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    esquema: dict[str, Any] = criar_app().openapi()
    return esquema


def test_openapi_versionado_esta_atualizado() -> None:
    versionado = (RAIZ / "openapi.json").read_text(encoding="utf-8")
    assert versionado == serializar(criar_app().openapi()), (
        "openapi.json desatualizado: rode `uv run python -m stur_api.openapi_export > openapi.json`"
    )


def test_openapi_tem_as_rotas(esquema: dict[str, Any]) -> None:
    for caminho, metodo in SEIS_ROTAS.items():
        assert metodo in esquema["paths"][caminho], caminho


def test_operation_ids_estaveis_e_legiveis(esquema: dict[str, Any]) -> None:
    ids = {
        (caminho, metodo): operacao["operationId"]
        for caminho, metodos in esquema["paths"].items()
        for metodo, operacao in metodos.items()
    }
    assert ids == OPERATION_IDS


def test_422_documenta_o_envelope_de_erro(esquema: dict[str, Any]) -> None:
    esquemas = esquema["components"]["schemas"]
    assert "HTTPValidationError" not in esquemas
    assert "ValidationError" not in esquemas
    assert set(esquemas["ErroConsulta"]["properties"]) == {
        "codigo",
        "mensagem",
        "detalhe",
        "campo",
    }
    for caminho in (
        "/api/v1/vendas",
        "/api/v1/reservas/{numero}",
        "/api/v1/reservas/{numero}/vendas/{idreserva}",
        "/api/v1/reservas/{numero}/vendas/{idreserva}/dado-cru",
    ):
        resposta = esquema["paths"][caminho]["get"]["responses"]["422"]
        referencia = resposta["content"]["application/json"]["schema"]["$ref"]
        assert referencia == "#/components/schemas/ErroConsulta", caminho


def test_erros_da_agi_e_404_documentados(esquema: dict[str, Any]) -> None:
    for caminho in (
        "/api/v1/vendas",
        "/api/v1/reservas/{numero}",
        "/api/v1/reservas/{numero}/vendas/{idreserva}",
        "/api/v1/reservas/{numero}/vendas/{idreserva}/dado-cru",
        "/api/v1/parametros",
    ):
        respostas = esquema["paths"][caminho]["get"]["responses"]
        for status in ("500", "502", "504"):
            referencia = respostas[status]["content"]["application/json"]["schema"]["$ref"]
            assert referencia == "#/components/schemas/ErroApi", (caminho, status)
    for caminho in (
        "/api/v1/reservas/{numero}/vendas/{idreserva}",
        "/api/v1/reservas/{numero}/vendas/{idreserva}/dado-cru",
    ):
        assert "404" in esquema["paths"][caminho]["get"]["responses"], caminho


def test_serializar_e_deterministico_e_termina_em_quebra_de_linha() -> None:
    texto = serializar({"b": 1, "a": "é"})
    assert texto == '{\n  "a": "é",\n  "b": 1\n}\n'
    assert json.loads(texto) == {"a": "é", "b": 1}


def test_main_escreve_o_contrato_em_utf8_no_stdout(
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    main()
    saida = capsysbinary.readouterr().out
    assert saida == serializar(criar_app().openapi()).encode("utf-8")
    assert saida.endswith(b"\n")
