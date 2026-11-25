import asyncio
import json
import logging
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from tests import fabrica
from tests.agi_falsa import AgiFalsa

D = Decimal
VENDA = "/api/v1/reservas/90000001/vendas/{}"


def _reembolso(id_venda: int, **campos: Any) -> dict[str, Any]:
    """Item de `reembolsoVinculado[]` que aponta para a venda `id_venda`."""
    base: dict[str, Any] = {
        "id": 1,
        "idDetalheItem": "1",
        "idReservaVinculada": id_venda,
        "nomePax": "PASSAGEIRO EXEMPLO",
        "numeroSR": "SR-EXEMPLO-1",
    }
    base.update(campos)
    return base


def _corpos(agi: AgiFalsa) -> list[dict[str, Any]]:
    return [json.loads(chamada.request.content) for chamada in agi.reservas.calls]


def test_reserva_com_varias_vendas(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [
        fabrica.venda(idreserva=1002),
        fabrica.venda(idreserva=1001),
        fabrica.venda(idreserva=1003, status="CANCELADA"),
    ]
    r = cliente_http.get("/api/v1/reservas/90000001").json()["reserva"]
    assert [v["resumo"]["idreserva"] for v in r["vendas"]] == [1001, 1002, 1003]
    assert [v["posicao"] for v in r["vendas"]] == [1, 2, 3]
    assert r["totais"]["quantidade"] == 3
    assert r["totais"]["quantidadeCanceladas"] == 1


def test_reserva_sem_vendas_e_200_vazia(cliente_http: TestClient, agi: AgiFalsa) -> None:
    r = cliente_http.get("/api/v1/reservas/90000002")  # a AGI só tem a 90000001
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["numero"] == 90000002
    assert corpo["reserva"]["numero"] == 90000002
    assert corpo["reserva"]["vendas"] == []
    assert corpo["reserva"]["totais"]["quantidade"] == 0
    assert corpo["reserva"]["totais"]["totalCliente"] == "0"
    assert corpo["dadosDoSturAte"] == "2026-11-18T09:30:00"  # sem vendas: a consulta pequena


def test_reserva_traz_lancamentos_e_instante(cliente_http: TestClient, agi: AgiFalsa) -> None:
    corpo = cliente_http.get("/api/v1/reservas/90000001").json()
    assert corpo["consultadoEm"] == "2026-11-25T10:00:00-03:00"
    assert corpo["dadosDoSturAte"] == "2026-11-01T09:00:00"
    venda = corpo["reserva"]["vendas"][0]
    assert venda["resumo"]["totalCliente"] == "1050.01"
    assert venda["recebimentos"] == [
        {
            "indice": 0,
            "valorExibido": "1050.01",
            "ehCredito": False,
            "situacao": "sem_saldo",
            "vencido": False,
            "cartaoRepassado": False,
        }
    ]
    assert venda["pagamentos"][0]["valorExibido"] == "990.00"
    assert corpo["reserva"]["totais"]["margem"] == "60.01"
    (pedido,) = _corpos(agi)  # uma chamada só, pelo número, na janela larga
    assert pedido["Reserva"] == 90000001
    assert pedido["TipoData"] == "EMISSAO"
    assert (pedido["DataInicial"], pedido["DataFinal"]) == ("2020-01-01", "2027-12-31")


def test_venda_traz_calculos_e_posicao(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # 2 vendas; abrir a 1002 → posicao 2, reserva.totais.quantidade 2, calculos.verificacao.fecha
    # True, servicos[0].cliente.total "1050.01"
    agi.vendas = [fabrica.venda(idreserva=1001), fabrica.venda(idreserva=1002)]
    r = cliente_http.get(VENDA.format(1002)).json()
    assert r["posicao"] == 2
    assert r["reserva"]["totais"]["quantidade"] == 2
    assert r["calculos"]["verificacao"]["fecha"] is True
    assert r["calculos"]["servicos"][0]["cliente"]["total"] == "1050.01"
    assert r["venda"]["idreserva"] == 1002
    assert r["consultadoEm"] == "2026-11-25T10:00:00-03:00"
    assert r["dadosDoSturAte"] == "2026-11-01T09:00:00"
    calculos = r["calculos"]
    assert calculos["tipo"] == "venda"
    assert calculos["totaisServicos"] == {
        "cliente": "1050.01",
        "fornecedor": "990.00",
        "margem": "60.01",
        "percentualLucro": "5.72",
    }
    assert calculos["percentualLucro"] == "5.72"
    assert calculos["totalPagamentos"] == "990.00"
    assert calculos["diferencaPagamentosFornecedor"] == "0.00"
    assert [s["indice"] for s in calculos["servicos"]] == [0]
    assert calculos["recebimentos"][0]["situacao"] == "sem_saldo"
    assert calculos["itinerario"] is None  # Diversos, sem trechos
    assert calculos["estadoServico"] is None  # sem datas de início e término
    assert calculos["avisos"] == []
    assert r["vinculos"] == {"fee": None, "reembolsos": []}
    assert r["camposDesconhecidos"] == []
    assert agi.reservas.call_count == 1  # a venda e as outras do número numa chamada só


def test_pagamentos_que_nao_cobrem_o_fornecedor(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # crédito do fornecedor abate o total dos pagamentos; a diferença sai negativa, sem aviso
    agi.vendas = [
        fabrica.venda(
            pagamentos=[
                fabrica.pagamento(valor=D("900.00")),
                fabrica.pagamento(uniqueid=2, forma=2, valor=D("10.00")),
            ]
        )
    ]
    calculos = cliente_http.get(VENDA.format(1001)).json()["calculos"]
    assert calculos["totalPagamentos"] == "890.00"
    assert calculos["diferencaPagamentosFornecedor"] == "-100.00"
    assert calculos["pagamentos"][1]["valorExibido"] == "-10.00"
    assert calculos["avisos"] == []


def test_venda_de_outro_numero_e_404(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [fabrica.venda(idreserva=1001), fabrica.venda(reserva=90000002, idreserva=1002)]
    for rota in (VENDA.format(1002), VENDA.format(1002) + "/dado-cru"):
        r = cliente_http.get(rota)
        assert r.status_code == 404
        assert r.json() == {
            "codigo": "venda_nao_encontrada",
            "mensagem": "Nenhuma venda com esse número de reserva e esse id interno.",
            "detalhe": None,
        }


def test_fee_vinculado_na_mesma_reserva(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # 1001 BILHETE com idreservavinculadafee=1002; 1002 TAXA FEE com 1001 → vinculos.fee
    # {idreserva 1002, produto "TAXA FEE", posicao 2, quantidade 2}
    agi.vendas = [
        fabrica.venda(idreserva=1001, nomeproduto="BILHETE EXEMPLO", idreservavinculadafee=1002),
        fabrica.venda(idreserva=1002, nomeproduto="TAXA FEE", idreservavinculadafee=1001),
    ]
    bilhete = cliente_http.get(VENDA.format(1001)).json()
    assert bilhete["vinculos"]["fee"] == {
        "idreserva": 1002,
        "numero": 90000001,
        "produto": "TAXA FEE",
        "posicao": 2,
        "quantidade": 2,
    }
    assert bilhete["calculos"]["avisos"] == []
    fee = cliente_http.get(VENDA.format(1002)).json()  # o vínculo de volta
    assert fee["vinculos"]["fee"] == {
        "idreserva": 1001,
        "numero": 90000001,
        "produto": "BILHETE EXEMPLO",
        "posicao": 1,
        "quantidade": 2,
    }
    assert fee["calculos"]["tipo"] == "fee"
    assert fee["calculos"]["avisos"] == [{"codigo": "venda_fee", "siglas": []}]
    assert agi.reservas.call_count == 2  # uma por venda aberta: o fee veio junto


def test_fee_com_vinculada_fora_do_numero_fica_sem_vinculo(
    cliente_http: TestClient, agi: AgiFalsa
) -> None:
    # o fee nunca liga números diferentes (PRD 8.4): não se busca a venda de fora
    agi.vendas = [fabrica.venda(idreserva=1002, nomeproduto="TAXA FEE", idreservavinculadafee=1009)]
    r = cliente_http.get(VENDA.format(1002)).json()
    assert r["vinculos"]["fee"] is None
    assert r["venda"]["idreservavinculadafee"] == 1009
    assert agi.reservas.call_count == 1


def test_reembolso_do_mesmo_numero_nao_chama_a_agi(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [
        fabrica.venda(idreserva=1001, nomeproduto="BILHETE EXEMPLO"),
        fabrica.venda(
            idreserva=1002, nomeproduto="REEMBOLSO EXEMPLO", reembolsoVinculado=[_reembolso(1001)]
        ),
    ]
    r = cliente_http.get(VENDA.format(1002)).json()
    assert r["vinculos"]["reembolsos"] == [
        {
            "id": 1,
            "numeroSR": "SR-EXEMPLO-1",
            "nomePax": "PASSAGEIRO EXEMPLO",
            "venda": {
                "idreserva": 1001,
                "numero": 90000001,
                "produto": "BILHETE EXEMPLO",
                "posicao": 1,
                "quantidade": 2,
            },
        }
    ]
    assert agi.reservas.call_count == 1


def test_reembolso_de_outro_numero_busca_por_id(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [
        fabrica.venda(idreserva=1001, reembolsoVinculado=[_reembolso(1005)]),
        fabrica.venda(reserva=90000002, idreserva=1005, nomeproduto="BILHETE EXEMPLO"),
    ]
    r = cliente_http.get(VENDA.format(1001)).json()
    assert r["vinculos"]["reembolsos"] == [
        {
            "id": 1,
            "numeroSR": "SR-EXEMPLO-1",
            "nomePax": "PASSAGEIRO EXEMPLO",
            "venda": {
                "idreserva": 1005,
                "numero": 90000002,
                "produto": "BILHETE EXEMPLO",
                "posicao": None,
                "quantidade": None,
            },
        }
    ]
    primeira, segunda = _corpos(agi)
    assert primeira["Reserva"] == 90000001
    assert "Id" not in primeira
    assert segunda["Id"] == 1005
    assert "Reserva" not in segunda
    assert segunda["TipoData"] == "EMISSAO"
    assert (segunda["DataInicial"], segunda["DataFinal"]) == ("2020-01-01", "2027-12-31")
    assert r["reserva"]["totais"]["quantidade"] == 1  # a venda de fora não entra na reserva


def test_reembolsos_buscados_ate_4_ao_mesmo_tempo(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # 7 reembolsos para 6 vendas de fora: 6 buscas por id, nunca mais de 4 ao mesmo tempo
    ids = [1011, 1012, 1013, 1014, 1015, 1016, 1011]
    agi.vendas = [
        fabrica.venda(reembolsoVinculado=[_reembolso(i, id=n) for n, i in enumerate(ids, 1)])
    ]
    padrao = agi.reservas.side_effect
    em_curso = 0
    maximo = 0

    async def responder(pedido: httpx.Request) -> httpx.Response:
        nonlocal em_curso, maximo
        corpo = json.loads(pedido.content)
        if "Id" not in corpo:
            resposta: httpx.Response = padrao(pedido)
            return resposta
        em_curso += 1
        maximo = max(maximo, em_curso)
        await asyncio.sleep(0.02)
        em_curso -= 1
        vinculada = fabrica.venda(reserva=90000002, idreserva=corpo["Id"])
        return httpx.Response(200, text=fabrica.resposta_agi([vinculada]))

    agi.reservas.side_effect = responder
    r = cliente_http.get(VENDA.format(1001)).json()
    vendas = [item["venda"]["idreserva"] for item in r["vinculos"]["reembolsos"]]
    assert vendas == ids
    assert agi.reservas.call_count == 1 + 6
    assert maximo == 4


@pytest.mark.parametrize(
    "falha",
    [
        httpx.ReadTimeout("x"),
        httpx.Response(500),
        httpx.Response(
            200, text=fabrica.resposta_agi([fabrica.venda(idreserva=1005, totalCliente="mil")])
        ),
        httpx.DecodingError("x"),
        httpx.Response(200, text=fabrica.resposta_agi([])),
    ],
    ids=["sem_resposta", "erro_500", "venda_invalida", "erro_httpx", "nao_achou"],
)
def test_reembolso_que_falha_nao_derruba_a_venda(
    cliente_http: TestClient, agi: AgiFalsa, falha: Exception | httpx.Response
) -> None:
    agi.vendas = [fabrica.venda(idreserva=1001, reembolsoVinculado=[_reembolso(1005)])]
    padrao = agi.reservas.side_effect

    def responder(pedido: httpx.Request) -> httpx.Response:
        if "Id" not in json.loads(pedido.content):
            resposta: httpx.Response = padrao(pedido)
            return resposta
        if isinstance(falha, Exception):
            raise falha
        return falha

    agi.reservas.side_effect = responder
    r = cliente_http.get(VENDA.format(1001))
    assert r.status_code == 200
    (reembolso,) = r.json()["vinculos"]["reembolsos"]
    assert reembolso["venda"] is None
    assert reembolso["numeroSR"] == "SR-EXEMPLO-1"
    assert agi.reservas.call_count == 2


def test_avisos_da_reservada(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # RESERVADA com comissões zeradas → avisos ["venda_reservada"], recebimentos todos "previsto"
    agi.vendas = [fabrica.venda(status="RESERVADA")]
    calculos = cliente_http.get(VENDA.format(1001)).json()["calculos"]
    assert calculos["avisos"] == [{"codigo": "venda_reservada", "siglas": []}]
    assert [lanc["situacao"] for lanc in calculos["recebimentos"]] == ["previsto"]
    assert [lanc["situacao"] for lanc in calculos["pagamentos"]] == ["previsto"]
    assert calculos["servicos"][0]["comissoesNaoApuradas"] is True  # a conta ainda diz isso


def test_avisos_atencao_antes_de_informacao(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # CONFIRMADA, tarifa do cliente em US$ convertida, a do fornecedor em EUR com câmbio 1,
    # comissões zeradas, e a soma dos serviços não fecha com os totais da API
    agi.vendas = [
        fabrica.venda(
            status="CONFIRMADA",
            detalheItem=[
                fabrica.servico(
                    siglaMoedaTarifa="US$", vlrCambio=D("5.000000000"), vlrTarifaTotal=D("100.00")
                ),
                fabrica.servico(siglaMoedaTarifap="EUR", vlrTarifaTotalp=D("10.00")),
                fabrica.servico(siglaMoedaTarifap="EUR", vlrTarifaTotalp=D("20.00")),
            ],
        )
    ]
    calculos = cliente_http.get(VENDA.format(1001)).json()["calculos"]
    assert calculos["avisos"] == [
        {"codigo": "conta_nao_fecha", "siglas": []},
        {"codigo": "moeda_estrangeira", "siglas": ["US$"]},
        {"codigo": "moeda_cambio_1", "siglas": ["EUR"]},
        {"codigo": "comissao_nao_apurada", "siglas": []},
    ]
    assert calculos["verificacao"]["fecha"] is False


def test_avisos_do_fee_cancelado(cliente_http: TestClient, agi: AgiFalsa) -> None:
    # cancelada não leva "comissão não apurada" (IA 9.5: só reservada ou confirmada)
    agi.vendas = [
        fabrica.venda(idreserva=1001, idreservavinculadafee=1002),
        fabrica.venda(
            idreserva=1002, status="CANCELADA", nomeproduto="TAXA FEE", idreservavinculadafee=1001
        ),
    ]
    calculos = cliente_http.get(VENDA.format(1002)).json()["calculos"]
    assert [a["codigo"] for a in calculos["avisos"]] == ["venda_fee", "venda_cancelada"]


def test_dado_cru_igual_ao_da_agi(cliente_http: TestClient, agi: AgiFalsa) -> None:
    r = cliente_http.get("/api/v1/reservas/90000001/vendas/1001/dado-cru")
    assert r.headers["content-type"].startswith("application/json")
    assert '"totalCliente": 1050.01' in r.text


def test_dado_cru_mantem_a_ordem_e_o_campo_novo(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [fabrica.venda(campoNovo=D("1.50")), fabrica.venda(idreserva=1002)]
    r = cliente_http.get(VENDA.format(1001) + "/dado-cru")
    assert r.status_code == 200
    chaves = [chave for chave, _ in json.loads(r.text, object_pairs_hook=lambda pares: pares)]
    assert chaves == list(fabrica.venda(campoNovo=None))  # a ordem em que a AGI mandou
    assert '"campoNovo": 1.50' in r.text  # número como veio, sem passar por float
    assert '"idreserva": 1002' not in r.text  # só a venda pedida
    assert agi.reservas.call_count == 1


def test_campo_novo_aparece_em_campos_desconhecidos(
    cliente_http: TestClient, agi: AgiFalsa
) -> None:
    venda = fabrica.venda(campoNovo="valor novo")
    venda["detalheItem"][0]["taxaNova"] = D("1.50")
    agi.vendas = [venda]
    r = cliente_http.get(VENDA.format(1001))
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["camposDesconhecidos"] == ["campoNovo", "detalheItem[].taxaNova"]
    assert corpo["venda"]["campoNovo"] == "valor novo"  # o campo novo não some da venda
    assert corpo["venda"]["detalheItem"][0]["taxaNova"] == "1.50"


def test_venda_com_os_nomes_da_agi(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [fabrica.venda(taxasAdministrativas=D("0.000000000"), dtcancelamento=None)]
    venda = cliente_http.get(VENDA.format(1001)).json()["venda"]
    assert venda["totalCliente"] == "1050.01"  # Decimal como texto, como no resto do contrato
    assert venda["taxasAdministrativas"] == "0.000000000"  # notação fixa, sem "0E-9"
    assert venda["detalheItem"][0]["vlrCambio"] == "1"
    assert venda["dtemissao"] == "2026-11-01 09:00:00"  # data da AGI como veio
    assert venda["dtcancelamento"] is None
    assert venda["nomefornec2"] == "FORNECEDOR EXEMPLO"
    assert venda["sistemaExterno"] is None  # campo que não veio sai null


def test_reserva_e_venda_sem_cache(cliente_http: TestClient, agi: AgiFalsa) -> None:
    for rota in ("/api/v1/reservas/90000001", VENDA.format(1001), VENDA.format(1001) + "/dado-cru"):
        cliente_http.get(rota)
        cliente_http.get(rota)
    assert agi.reservas.call_count == 6  # cada abertura é uma consulta nova (PRD RF-10)


def test_venda_com_tipo_errado_e_502(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [fabrica.venda(), fabrica.venda(idreserva=1002, totalCliente="mil e cinquenta")]
    r = cliente_http.get(VENDA.format(1001))
    assert r.status_code == 502
    assert r.json()["detalhe"] == ["venda 1002: totalCliente: decimal_parsing"]
    assert "mil e cinquenta" not in r.text
    cru = cliente_http.get(VENDA.format(1002) + "/dado-cru")  # o dado cru mostra como veio
    assert cru.status_code == 200
    assert '"totalCliente": "mil e cinquenta"' in cru.text


def test_reserva_com_venda_invalida_aponta_a_venda(cliente_http: TestClient, agi: AgiFalsa) -> None:
    agi.vendas = [fabrica.venda(), fabrica.venda(idreserva=1002, totalCliente="mil e cinquenta")]
    r = cliente_http.get("/api/v1/reservas/90000001")
    assert r.status_code == 502
    assert r.json()["detalhe"] == ["venda 1002: totalCliente: decimal_parsing"]
    assert "mil e cinquenta" not in r.text


@pytest.mark.parametrize(
    ("falha", "classe"),
    [
        (httpx.ReadTimeout("x"), "ApiSturSemResposta"),
        # o cliente traduz o httpx que sobrava: já não chega cru à busca por id
        (httpx.DecodingError("x"), "ApiSturRespostaInvalida"),
    ],
    ids=["traduzida", "httpx_traduzido_pelo_cliente"],
)
def test_busca_por_id_que_falha_loga_so_idreserva_e_classe(
    cliente_http: TestClient,
    agi: AgiFalsa,
    caplog: pytest.LogCaptureFixture,
    falha: Exception,
    classe: str,
) -> None:
    agi.vendas = [fabrica.venda(idreserva=1001, reembolsoVinculado=[_reembolso(1005)])]
    padrao = agi.reservas.side_effect

    def responder(pedido: httpx.Request) -> httpx.Response:
        if "Id" not in json.loads(pedido.content):
            resposta: httpx.Response = padrao(pedido)
            return resposta
        raise falha

    agi.reservas.side_effect = responder
    caplog.set_level(logging.DEBUG)
    assert cliente_http.get(VENDA.format(1001)).status_code == 200
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    (aviso,) = avisos
    assert aviso.name == "servico.consultas"
    assert aviso.getMessage() == f"busca_por_id_falhou idreserva=1005 erro={classe}"
    assert aviso.exc_info is None
