from decimal import Decimal
from typing import Any

from stur_api.config import Configuracao
from stur_api.dominio.vendas import (
    ResumoVenda,
    ordenar_por_lancamento,
    resumir,
    tipo_da_venda,
    totais_da_reserva,
)
from tests import fabrica
from tests.fabrica import validar_venda

D = Decimal
CONFIG = Configuracao(
    _env_file=None,
    stur_api_url="https://agi.exemplo.invalid",
    stur_api_usuario="usuario-de-teste",
    stur_api_senha="senha-de-teste",
)


def _resumo(**campos: Any) -> ResumoVenda:
    return resumir(validar_venda(fabrica.venda(**campos)), CONFIG)


def test_incentivo_pelo_produto(config: Configuracao) -> None:
    venda = validar_venda(fabrica.venda(nomeproduto="Incentivo"))
    assert tipo_da_venda(venda, config) == "incentivo"


def test_fee_precisa_do_vinculo(config: Configuracao) -> None:
    sem_vinculo = validar_venda(fabrica.venda(nomeproduto="TAXA FEE", idreservavinculadafee=0))
    com_vinculo = validar_venda(fabrica.venda(nomeproduto="Taxa  Fee", idreservavinculadafee=1001))
    assert tipo_da_venda(sem_vinculo, config) == "venda"
    assert tipo_da_venda(com_vinculo, config) == "fee"


def test_produto_comum_e_venda(config: Configuracao) -> None:
    assert tipo_da_venda(validar_venda(fabrica.venda()), config) == "venda"
    assert tipo_da_venda(validar_venda(fabrica.venda(nomeproduto=None)), config) == "venda"


def test_resumo_traz_os_valores_da_api_e_o_tipo(config: Configuracao) -> None:
    r = resumir(validar_venda(fabrica.venda()), config)
    assert (r.numero, r.idreserva, r.situacao) == (90000001, 1001, "fechada")
    assert (r.produto, r.classificacao, r.categoria) == ("PRODUTO EXEMPLO", "Diversos", "Nacional")
    assert (r.cliente, r.fornecedor, r.fornecedor2) == (
        "CLIENTE EXEMPLO LTDA",
        "FORNECEDOR EXEMPLO",
        "FORNECEDOR EXEMPLO",
    )
    assert r.emissor == "EMISSOR EXEMPLO"
    assert r.data_emissao == r.data_confirmacao == r.data_alteracao == fabrica.DATA_PADRAO
    assert (r.total_cliente, r.total_fornecedor, r.margem) == (
        D("1050.01"),
        D("990.00"),
        D("60.01"),
    )
    assert r.percentual_lucro == D("5.72")
    assert r.conta_fecha is True
    assert r.tipo == "venda"
    assert r.id_venda_fee is None


def test_resumo_conta_que_nao_fecha(config: Configuracao) -> None:
    r = resumir(validar_venda(fabrica.venda(totalCliente=D("2000.00"))), config)
    assert r.conta_fecha is False


def test_situacao_em_minusculas_e_sem_status(config: Configuracao) -> None:
    assert resumir(validar_venda(fabrica.venda(status="CANCELADA")), config).situacao == "cancelada"
    assert resumir(validar_venda(fabrica.venda(status=None)), config).situacao is None


def test_venda_com_vinculo_de_fee_guarda_o_id_da_venda_fee(config: Configuracao) -> None:
    venda = validar_venda(fabrica.venda(idreservavinculadafee=1002))
    assert resumir(venda, config).id_venda_fee == 1002
    fee = validar_venda(fabrica.venda(nomeproduto="TAXA FEE", idreservavinculadafee=1001))
    r_fee = resumir(fee, config)
    assert (r_fee.tipo, r_fee.id_venda_fee) == ("fee", None)


def test_resumo_sem_campos_nao_quebra(config: Configuracao) -> None:
    r = resumir(validar_venda({}), config)
    assert r.total_cliente == r.total_fornecedor == r.margem == D("0")
    assert r.percentual_lucro is None
    assert r.passageiros == []
    assert r.conta_fecha is True


def test_ordem_de_lancamento_pelo_idreserva() -> None:
    vendas = [validar_venda(fabrica.venda(idreserva=i)) for i in (1003, 1001, 1002)]
    assert [v.idreserva for v in ordenar_por_lancamento(vendas)] == [1001, 1002, 1003]


def test_totais_da_reserva_sem_canceladas() -> None:
    resumos = [
        _resumo(
            idreserva=1001,
            totalCliente=D("1000"),
            totalFornecedor=D("900"),
            margemLucroBruta=D("100"),
        ),
        _resumo(
            idreserva=1002, totalCliente=D("500"), totalFornecedor=D("500"), margemLucroBruta=D("0")
        ),
        _resumo(
            idreserva=1003,
            status="CANCELADA",
            totalCliente=D("300"),
            totalFornecedor=D("200"),
            margemLucroBruta=D("100"),
        ),
    ]
    t = totais_da_reserva(resumos)
    assert (t.quantidade, t.quantidade_canceladas) == (3, 1)
    assert (t.total_cliente, t.total_fornecedor, t.margem) == (D("1500"), D("1400"), D("100"))
    assert t.percentual_lucro == D("6.67")


def test_margem_negativa_entra_na_soma() -> None:
    resumos = [
        _resumo(
            idreserva=1001,
            totalCliente=D("1000"),
            totalFornecedor=D("900"),
            margemLucroBruta=D("100"),
        ),
        _resumo(
            idreserva=1002,
            totalCliente=D("200"),
            totalFornecedor=D("250"),
            margemLucroBruta=D("-50"),
        ),
    ]
    t = totais_da_reserva(resumos)
    assert t.margem == D("50")
    assert t.percentual_lucro == D("4.17")


def test_totais_com_total_cliente_zero_nao_tem_percentual() -> None:
    t = totais_da_reserva(
        [_resumo(totalCliente=D("0"), totalFornecedor=D("0"), margemLucroBruta=D("0"))]
    )
    assert t.percentual_lucro is None
    assert totais_da_reserva([]).quantidade == 0


def test_passageiros_distintos_na_ordem(config: Configuracao) -> None:
    venda = validar_venda(
        fabrica.venda(
            detalheItem=[
                fabrica.servico(nomePaxCompleto="MARIA EXEMPLO DA SILVA"),
                fabrica.servico(nomePaxCompleto=None, nomePax="JOAO EXEMPLO"),
                fabrica.servico(nomePaxCompleto="MARIA EXEMPLO DA SILVA"),
                fabrica.servico(nomePaxCompleto="", nomePax=""),
                fabrica.servico(nomePaxCompleto="ANA EXEMPLO"),
            ]
        )
    )
    assert resumir(venda, config).passageiros == [
        "MARIA EXEMPLO DA SILVA",
        "JOAO EXEMPLO",
        "ANA EXEMPLO",
    ]
