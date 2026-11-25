import json
from decimal import Decimal

import httpx
from fastapi.testclient import TestClient

from stur_api.main import criar_app
from stur_api.servicos.consultas import ServicoConsulta
from tests import fabrica
from tests.agi_falsa import AgiFalsa

D = Decimal


def test_consulta_por_periodo(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [
        fabrica.venda(idreserva=1001, dtemissao="2026-11-10 10:00:00"),
        fabrica.venda(idreserva=1002, dtemissao="2026-11-12 10:00:00"),
        fabrica.venda(idreserva=1003, status="CANCELADA"),
        fabrica.venda(idreserva=1004, nomeproduto="INCENTIVO", totalCliente=D("0")),
    ]
    r = cliente_http.get(
        "/api/v1/vendas", params={"tipoData": "emissao", "de": "2026-11-01", "ate": "2026-11-17"}
    ).json()
    assert [v["idreserva"] for v in r["vendas"]][:2] == [1002, 1001]
    assert (
        r["resumo"]["quantidade"] == 2
        and r["resumo"]["incentivos"]["quantidade"] == 1
        and r["resumo"]["canceladas"] == 1
    )
    assert r["vendas"][0]["totalCliente"] == "1050.01"  # Decimal como texto


def test_periodo_longo_responde_422_sem_chamar_a_agi(
    cliente_http: TestClient, agi: AgiFalsa
) -> None:
    r = cliente_http.get("/api/v1/vendas", params={"de": "2026-10-01", "ate": "2026-11-01"})
    assert (
        r.status_code == 422 and r.json()["codigo"] == "periodo_longo" and r.json()["campo"] == "de"
    )
    assert agi.reservas.call_count == 0


def test_reserva_nao_numerica_e_parametro_invalido(cliente_http: TestClient, agi: AgiFalsa) -> None:
    r = cliente_http.get("/api/v1/vendas", params={"reserva": "9000x001"})
    assert r.status_code == 422
    corpo = r.json()
    assert corpo["codigo"] == "parametro_invalido"
    assert corpo["mensagem"] == "Um parâmetro da consulta está num formato inválido."
    assert corpo["campo"] == "reserva"
    assert corpo["detalhe"] == ["reserva: int_parsing"]
    assert "9000x001" not in r.text  # o valor recebido não volta na resposta
    assert agi.reservas.call_count == 0


def test_periodo_depois_da_copia_volta_vazio(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = []
    agi.ultima_copia = "2026-11-18 09:30:00"
    r = cliente_http.get("/api/v1/vendas", params={"de": "2026-11-20", "ate": "2026-11-24"}).json()
    assert (
        r["vendas"] == []
        and r["periodoPassaDaCopia"] is True
        and r["dadosDoSturAte"] == "2026-11-18T09:30:00"
    )


def test_periodo_ate_o_dia_da_copia_nao_passa_dela(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [fabrica.venda(dtalteracaovinculado="2026-11-18 09:30:00")]
    r = cliente_http.get("/api/v1/vendas", params={"de": "2026-11-01", "ate": "2026-11-18"}).json()
    assert r["dadosDoSturAte"] == "2026-11-18T09:30:00"
    assert r["periodoPassaDaCopia"] is False


def test_filtro_por_nome_no_backend(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # cliente="acai" acha "AÇAÍ"
    agi.vendas = [
        fabrica.venda(idreserva=1001, nomecliente="AÇAÍ EXEMPLO LTDA"),
        fabrica.venda(idreserva=1002),
    ]
    r = cliente_http.get("/api/v1/vendas", params={"reserva": "90000001", "cliente": "acai"}).json()
    assert [v["idreserva"] for v in r["vendas"]] == [1001]
    assert "acai" not in agi.reservas.calls.last.request.content.decode()  # a AGI não recebe o nome


def test_consulta_ecoada_e_instante_da_consulta(cliente_http: TestClient, agi: AgiFalsa) -> None:
    r = cliente_http.get(
        "/api/v1/vendas", params={"reserva": "90000001", "situacao": ["fechada", "cancelada"]}
    ).json()
    assert r["consulta"] == {
        "reserva": 90000001,
        "tipoData": "emissao",
        "de": None,
        "ate": None,
        "situacao": ["cancelada", "fechada"],
        "classificacao": [],
        "fornecedor": None,
        "cliente": None,
        "emissor": None,
        "janelaLarga": True,
    }
    assert r["consultadoEm"] == "2026-11-25T10:00:00-03:00"
    assert r["dadosDoSturAte"] == "2026-11-01T09:00:00"
    assert r["periodoPassaDaCopia"] is False
    linha = r["vendas"][0]
    assert linha["vendasNoResultado"] == 1
    assert linha["fee"] is None
    assert linha["percentualLucro"] == "5.72"
    assert linha["contaFecha"] is True


def test_cache_e_atualizar(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # duas consultas iguais → 1 chamada à AGI; a terceira com atualizar=true → 2 chamadas
    params = {"reserva": "90000001"}
    cliente_http.get("/api/v1/vendas", params=params)
    cliente_http.get("/api/v1/vendas", params=params)
    assert agi.reservas.call_count == 1
    cliente_http.get("/api/v1/vendas", params={**params, "atualizar": "true"})
    assert agi.reservas.call_count == 2
    cliente_http.get("/api/v1/vendas", params=params)
    assert agi.reservas.call_count == 2  # o resultado atualizado ficou guardado
    cliente_http.get("/api/v1/vendas", params={**params, "cliente": "exemplo"})
    assert agi.reservas.call_count == 3  # a chave é a consulta inteira (R7)


def test_fee_com_produto_da_vinculada_no_resultado(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [
        fabrica.venda(idreserva=1001, nomeproduto="BILHETE EXEMPLO", idreservavinculadafee=1002),
        fabrica.venda(idreserva=1002, nomeproduto="TAXA FEE", idreservavinculadafee=1001),
    ]
    r = cliente_http.get("/api/v1/vendas", params={"reserva": "90000001"}).json()
    linhas = {v["idreserva"]: v for v in r["vendas"]}
    assert linhas[1002]["tipo"] == "fee"
    assert linhas[1002]["fee"] == {"idreserva": 1001, "produto": "BILHETE EXEMPLO"}
    assert linhas[1001]["fee"] is None
    assert linhas[1001]["idVendaFee"] == 1002
    assert linhas[1001]["vendasNoResultado"] == 2


def test_fee_sem_a_vinculada_no_resultado(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [
        fabrica.venda(
            idreserva=1001,
            nomeproduto="BILHETE EXEMPLO",
            classificacaoproduto="Aereo",
            idreservavinculadafee=1002,
        ),
        fabrica.venda(idreserva=1002, nomeproduto="TAXA FEE", idreservavinculadafee=1001),
    ]
    r = cliente_http.get(
        "/api/v1/vendas", params={"reserva": "90000001", "classificacao": "diversos"}
    ).json()
    assert [v["idreserva"] for v in r["vendas"]] == [1002]
    assert r["vendas"][0]["fee"] == {"idreserva": 1001, "produto": None}
    assert r["vendas"][0]["vendasNoResultado"] == 1


def test_agi_sem_resposta_e_504_com_a_mensagem(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.reservas.side_effect = httpx.ReadTimeout("x")
    r = cliente_http.get("/api/v1/vendas", params={"reserva": "90000001"})
    assert (
        r.status_code == 504
        and r.json()["codigo"] == "api_stur_sem_resposta"
        and "30 segundos" in r.json()["mensagem"]
    )


def test_venda_com_tipo_errado_e_502_sem_o_valor(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [fabrica.venda(), fabrica.venda(idreserva=1002, totalCliente="mil e cinquenta")]
    r = cliente_http.get("/api/v1/vendas", params={"reserva": "90000001"})
    assert r.status_code == 502
    assert r.json()["codigo"] == "api_stur_resposta_invalida"
    assert r.json()["detalhe"] == ["venda 1002: totalCliente: decimal_parsing"]  # aponta a venda
    assert "mil e cinquenta" not in r.text


def test_erro_inesperado_e_500_sem_o_texto_do_erro(servico: ServicoConsulta, agi: AgiFalsa) -> None:
    agi.reservas.side_effect = RuntimeError("texto-interno-do-erro")
    with TestClient(criar_app(servico), raise_server_exceptions=False) as http:
        r = http.get("/api/v1/vendas", params={"reserva": "90000001"})
    assert r.status_code == 500
    assert r.json() == {
        "codigo": "erro_interno",
        "mensagem": "Algo deu errado nesta aplicação, não na API do Stur.",
        "detalhe": None,
    }


def test_consulta_por_alteracao_com_numero_traz_as_vendas_do_numero(
    cliente_http: TestClient, agi: AgiFalsa
) -> None:
    # ALTERACAO com 100 itens por página é também a forma da consulta pequena da data da cópia;
    # com `Reserva` no pedido, a AGI falsa responde pelo número (R18)
    agi.vendas = [fabrica.venda(reserva=90000002, idreserva=1002)]
    r = cliente_http.get(
        "/api/v1/vendas",
        params={
            "reserva": "90000002",
            "tipoData": "alteracao",
            "de": "2026-11-01",
            "ate": "2026-11-17",
        },
    ).json()
    assert [v["idreserva"] for v in r["vendas"]] == [1002]


def test_situacao_unica_vai_a_agi_em_maiusculas(cliente_http: TestClient, agi: AgiFalsa) -> None:
    cliente_http.get("/api/v1/vendas", params={"reserva": "90000001", "situacao": "fechada"})
    assert json.loads(agi.reservas.calls.last.request.content)["Status"] == "FECHADA"
