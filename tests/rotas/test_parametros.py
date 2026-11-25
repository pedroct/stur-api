import json

import httpx
from fastapi.testclient import TestClient

from tests.agi_falsa import AgiFalsa
from tests.conftest import RelogioFixo


def test_parametros(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # 31, 20, [20, 50, 100], dadosDoSturAte da consulta pequena
    r = cliente_http.get("/api/v1/parametros")
    assert r.status_code == 200
    assert r.json() == {
        "periodoMaximoDias": 31,
        "linhasPorPagina": 20,
        "opcoesPorPagina": [20, 50, 100],
        "tempoLimiteSegundos": 30,
        "dadosDoSturAte": "2026-11-18T09:30:00",
    }
    corpo = json.loads(agi.reservas.calls.last.request.content)
    assert {k: corpo[k] for k in ("TipoData", "ItensPorPagina", "Pagina")} == {
        "TipoData": "ALTERACAO",
        "ItensPorPagina": 100,
        "Pagina": 1,
    }
    assert (corpo["DataInicial"], corpo["DataFinal"]) == ("2020-01-01", "2027-12-31")


def test_parametros_guarda_a_data_por_5_minutos(
    cliente_http: TestClient, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    cliente_http.get("/api/v1/parametros")
    relogio.avancar(299)
    cliente_http.get("/api/v1/parametros")
    assert agi.reservas.call_count == 1
    relogio.avancar(1)
    cliente_http.get("/api/v1/parametros")
    assert agi.reservas.call_count == 2


def test_parametros_usa_a_data_vista_na_ultima_consulta(
    cliente_http: TestClient, agi: AgiFalsa
) -> None:
    cliente_http.get("/api/v1/vendas", params={"reserva": "90000001"})
    r = cliente_http.get("/api/v1/parametros").json()
    assert r["dadosDoSturAte"] == "2026-11-01T09:00:00"
    assert agi.reservas.call_count == 1  # só a consulta de vendas; nenhuma consulta pequena


def test_parametros_sem_a_data_quando_a_agi_falha(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.reservas.side_effect = httpx.ReadTimeout("x")
    r = cliente_http.get("/api/v1/parametros")
    assert r.status_code == 200
    assert r.json()["dadosDoSturAte"] is None


def test_parametros_nao_repete_a_consulta_que_falhou(
    cliente_http: TestClient, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    agi.reservas.side_effect = httpx.ReadTimeout("x")
    cliente_http.get("/api/v1/parametros")
    relogio.avancar(30)
    assert cliente_http.get("/api/v1/parametros").json()["dadosDoSturAte"] is None
    assert agi.reservas.call_count == 1  # a falha fica guardada por 60 s (R18)
