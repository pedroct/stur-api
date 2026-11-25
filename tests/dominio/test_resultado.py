from datetime import date
from decimal import Decimal
from typing import Any

from stur_api.dominio.consulta import ConsultaVendas
from stur_api.dominio.resultado import (
    aplicar_filtros,
    ordenar_resultado,
    resumir_resultado,
    vendas_no_resultado,
)
from stur_api.dominio.vendas import ResumoVenda

D = Decimal


def _r(**campos: Any) -> ResumoVenda:
    base: dict[str, Any] = {
        "numero": 90000001,
        "idreserva": 1001,
        "produto": "PASSAGEM",
        "classificacao": "Diversos",
        "categoria": None,
        "cliente": "CLIENTE EXEMPLO LTDA",
        "fornecedor": "FORNECEDOR EXEMPLO",
        "fornecedor2": None,
        "emissor": "EMISSOR EXEMPLO",
        "data_emissao": "2026-11-01 09:00:00",
        "data_confirmacao": None,
        "data_alteracao": None,
        "situacao": "fechada",
        "total_cliente": D("0"),
        "total_fornecedor": D("0"),
        "margem": D("0"),
        "percentual_lucro": None,
        "conta_fecha": True,
        "tipo": "venda",
        "id_venda_fee": None,
        "passageiros": [],
    }
    base.update(campos)
    return ResumoVenda(**base)


def _consulta(**campos: Any) -> ConsultaVendas:
    return ConsultaVendas(campos.pop("reserva", None), **campos)


def test_fornecedor_casa_com_o_fornecedor_2() -> None:
    a = _r(idreserva=1001, fornecedor="OUTRO FORNECEDOR", fornecedor2="FORNECEDOR EXEMPLO")
    b = _r(idreserva=1002, fornecedor="FORNECEDOR EXEMPLO", fornecedor2=None)
    c = _r(idreserva=1003, fornecedor="OUTRO FORNECEDOR", fornecedor2=None)
    achados = aplicar_filtros([a, b, c], _consulta(fornecedor="exemplo"))
    assert [r.idreserva for r in achados] == [1001, 1002]


def test_filtro_de_texto_vazio_nao_esconde_campos_nulos() -> None:
    sem_nada = _r(cliente=None, fornecedor=None, fornecedor2=None, emissor=None)
    for vazio in (None, ""):
        c = _consulta(fornecedor=vazio, cliente=vazio, emissor=vazio)
        assert aplicar_filtros([sem_nada], c) == [sem_nada]


def test_filtro_de_texto_ignora_acento_e_caixa_e_exclui_nulos() -> None:
    com = _r(idreserva=1001, cliente="JOSÉ DA SILVA")
    sem = _r(idreserva=1002, cliente=None)
    assert aplicar_filtros([com, sem], _consulta(cliente="jose")) == [com]


def test_filtro_de_emissor() -> None:
    a = _r(idreserva=1001, emissor="EMISSOR EXEMPLO")
    b = _r(idreserva=1002, emissor="OUTRA PESSOA")
    assert aplicar_filtros([a, b], _consulta(emissor="exemplo")) == [a]


def test_filtro_de_situacao_e_classificacao() -> None:
    a = _r(idreserva=1001, situacao="fechada", classificacao="Aereo")
    b = _r(idreserva=1002, situacao="cancelada", classificacao="Hotelaria")
    c = _r(idreserva=1003, situacao="reservada", classificacao="Locacao")
    d = _r(idreserva=1004, situacao=None, classificacao=None)
    todas = [a, b, c, d]
    por_situacao = _consulta(situacoes=frozenset({"fechada", "cancelada"}))
    assert aplicar_filtros(todas, por_situacao) == [a, b]
    por_classe = _consulta(classificacoes=frozenset({"aereo", "locacao"}))
    assert aplicar_filtros(todas, por_classe) == [a, c]
    assert aplicar_filtros(todas, _consulta()) == todas


def test_resumo_separa_incentivos_e_canceladas() -> None:
    resumos = [
        _r(idreserva=1001, total_cliente=D("1000"), margem=D("100")),
        _r(idreserva=1002, total_cliente=D("500"), margem=D("50")),
        _r(idreserva=1003, situacao="cancelada", total_cliente=D("900"), margem=D("90")),
        _r(idreserva=1004, tipo="incentivo", total_cliente=D("0"), margem=D("300")),
    ]
    r = resumir_resultado(resumos)
    assert r.quantidade == 2
    assert r.total_cliente == D("1500")
    assert r.margem == D("150")
    assert r.percentual_lucro == D("10.00")
    assert r.canceladas == 1
    assert r.incentivos.quantidade == 1
    assert r.incentivos.valor == D("300")
    assert r.incentivos.margem_com_incentivos == D("450")
    assert r.incentivos.percentual_com_incentivos == D("30.00")


def test_incentivo_cancelado_nao_soma_no_valor() -> None:
    resumos = [
        _r(idreserva=1001, total_cliente=D("1000"), margem=D("100")),
        _r(idreserva=1002, tipo="incentivo", margem=D("300")),
        _r(idreserva=1003, tipo="incentivo", situacao="cancelada", margem=D("200")),
    ]
    r = resumir_resultado(resumos)
    assert r.incentivos.quantidade == 1
    assert r.incentivos.valor == D("300")
    assert r.canceladas == 1


def test_fee_entra_na_quantidade_no_total_e_na_margem() -> None:
    resumos = [
        _r(idreserva=1001, total_cliente=D("1000"), margem=D("100")),
        _r(idreserva=1002, tipo="fee", total_cliente=D("100"), margem=D("100")),
    ]
    r = resumir_resultado(resumos)
    assert r.quantidade == 2
    assert r.total_cliente == D("1100")
    assert r.margem == D("200")
    assert r.percentual_lucro == D("18.18")
    assert r.incentivos.margem_com_incentivos == D("200")


def test_canceladas_contam_toda_linha_cancelada_de_qualquer_tipo() -> None:
    resumos = [
        _r(idreserva=1001, total_cliente=D("1000"), margem=D("100")),
        _r(idreserva=1002, situacao="cancelada", total_cliente=D("900"), margem=D("90")),
        _r(idreserva=1003, tipo="fee", situacao="cancelada", total_cliente=D("50"), margem=D("50")),
        _r(idreserva=1004, tipo="incentivo", situacao="cancelada", margem=D("200")),
    ]
    r = resumir_resultado(resumos)
    assert r.canceladas == 3
    assert r.quantidade == 1
    assert r.total_cliente == D("1000")
    assert r.incentivos.quantidade == 0
    assert r.incentivos.valor == D("0")


def test_resumo_vazio_nao_divide_por_zero() -> None:
    r = resumir_resultado([])
    assert (r.quantidade, r.total_cliente, r.margem, r.nao_fecham, r.canceladas) == (
        0,
        D("0"),
        D("0"),
        0,
        0,
    )
    assert r.percentual_lucro is None
    assert r.incentivos.percentual_com_incentivos is None


def test_nao_fecham_conta_todas_as_linhas() -> None:
    resumos = [
        _r(idreserva=1001, conta_fecha=False),
        _r(idreserva=1002, conta_fecha=False, situacao="cancelada"),
        _r(idreserva=1003, conta_fecha=False, tipo="incentivo"),
        _r(idreserva=1004, conta_fecha=True),
    ]
    assert resumir_resultado(resumos).nao_fecham == 3


def test_ordem_por_data_mais_recente_primeiro() -> None:
    antiga = _r(idreserva=1001, data_emissao="2026-11-01 09:00:00")
    nova = _r(idreserva=1002, data_emissao="2026-11-03T08:00:00")
    empate_a = _r(idreserva=1003, data_emissao="2026-11-02 10:00:00")
    empate_b = _r(idreserva=1004, data_emissao="2026-11-02T10:00:00")
    sem_data = _r(idreserva=1005, data_emissao=None)
    sem_data_1899 = _r(idreserva=1006, data_emissao="1899-12-30T00:00:00")
    c = _consulta(de=date(2026, 11, 1), ate=date(2026, 11, 5))
    ordem = ordenar_resultado([antiga, sem_data, empate_a, nova, sem_data_1899, empate_b], c)
    assert [r.idreserva for r in ordem] == [1002, 1004, 1003, 1001, 1006, 1005]


def test_ordem_usa_a_data_do_tipo_consultado() -> None:
    a = _r(
        idreserva=1001, data_emissao="2026-11-09 00:00:00", data_confirmacao="2026-11-01 00:00:00"
    )
    b = _r(
        idreserva=1002, data_emissao="2026-11-01 00:00:00", data_confirmacao="2026-11-02 00:00:00"
    )
    c = _consulta(tipo_data="confirmacao", de=date(2026, 11, 1), ate=date(2026, 11, 5))
    assert [r.idreserva for r in ordenar_resultado([a, b], c)] == [1002, 1001]
    c = _consulta(tipo_data="alteracao", de=date(2026, 11, 1), ate=date(2026, 11, 5))
    alterada = _r(idreserva=1003, data_alteracao="2026-11-04 00:00:00")
    assert [r.idreserva for r in ordenar_resultado([a, alterada], c)] == [1003, 1001]


def test_so_numero_ordena_por_lancamento() -> None:
    a = _r(idreserva=1003)
    b = _r(idreserva=1001)
    c = _r(idreserva=1002)
    assert [r.idreserva for r in ordenar_resultado([a, b, c], _consulta(reserva=90000001))] == [
        1001,
        1002,
        1003,
    ]


def test_vendas_no_resultado_conta_linhas_por_numero() -> None:
    resumos = [
        _r(numero=90000001, idreserva=1001),
        _r(numero=90000001, idreserva=1002),
        _r(numero=90000002, idreserva=1003),
    ]
    assert vendas_no_resultado(resumos) == {90000001: 2, 90000002: 1}
