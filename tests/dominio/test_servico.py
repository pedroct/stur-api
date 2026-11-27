from datetime import date
from typing import Any

from stur_api.dominio.servico import ResumoServico, resumo_do_servico
from tests import fabrica
from tests.fabrica import validar_venda


def _resumo(**campos: Any) -> ResumoServico | None:
    return resumo_do_servico(validar_venda(fabrica.venda(**campos)))


def test_sem_detalhe_e_sem_trechos_nao_ha_resumo() -> None:
    assert _resumo(detalheItem=[], trechos=[]) is None
    assert _resumo(detalheItem=None, trechos=None) is None


def test_resumo_do_servico_hotel() -> None:
    resumo = _resumo(
        classificacaoproduto="Hotelaria",
        detalheItem=[
            fabrica.servico(
                dtEntrada="2026-11-26 00:00:00",
                dtSaida="2026-12-03 00:00:00",
                apartamentos=[
                    fabrica.apartamento(qtdeDiarias=7),
                    fabrica.apartamento(qtdeDiarias=7),
                ],
            )
        ],
    )
    assert resumo == ResumoServico(1, date(2026, 11, 26), date(2026, 12, 3), [], 7, None)


def test_hotel_usa_o_maior_numero_de_diarias_do_primeiro_servico() -> None:
    resumo = _resumo(
        classificacaoproduto="Hotelaria",
        detalheItem=[
            fabrica.servico(
                apartamentos=[
                    fabrica.apartamento(qtdeDiarias=3),
                    fabrica.apartamento(qtdeDiarias=5),
                    fabrica.apartamento(qtdeDiarias=None),
                ]
            ),
            fabrica.servico(apartamentos=[fabrica.apartamento(qtdeDiarias=30)]),
        ],
    )
    assert resumo is not None
    assert (resumo.quantidade, resumo.diarias) == (2, 5)


def test_hotel_sem_apartamentos_nao_tem_diarias() -> None:
    resumo = _resumo(
        classificacaoproduto="Hotelaria", detalheItem=[fabrica.servico(apartamentos=None)]
    )
    assert resumo is not None
    assert resumo.diarias is None


def test_locacao_usa_as_diarias_do_primeiro_servico() -> None:
    resumo = _resumo(
        classificacaoproduto="Locação",
        detalheItem=[
            fabrica.servico(
                dtRetirada="2026-12-01 10:00:00", dtDevolucao="2026-12-04 10:00:00", qtdeDiarias=3
            ),
            fabrica.servico(qtdeDiarias=9),
        ],
    )
    assert resumo == ResumoServico(2, date(2026, 12, 1), date(2026, 12, 4), [], 3, None)


def test_resumo_do_servico_aereo_sem_datas() -> None:
    resumo = _resumo(
        classificacaoproduto="Aéreo",
        trechos=[
            fabrica.trecho(1, "FOR", "FCO", None, None),
            fabrica.trecho(2, "FCO", "FOR", None, None),
        ],
    )
    assert resumo is not None
    assert resumo.rota == [["FOR", "FCO", "FOR"]]
    assert resumo.inicio is None
    assert resumo.fim is None
    assert resumo.diarias is None
    assert resumo.descricao is None


def test_resumo_do_servico_dois_trajetos() -> None:
    resumo = _resumo(
        classificacaoproduto="Aéreo",
        trechos=[
            fabrica.trecho(1, "FOR", "GRU", "2026-12-01 06:00:00", "2026-12-01 09:00:00"),
            fabrica.trecho(2, "GIG", "FOR", "2026-12-04 06:00:00", "2026-12-04 09:00:00"),
        ],
    )
    assert resumo is not None
    assert resumo.rota == [["FOR", "GRU"], ["GIG", "FOR"]]
    assert (resumo.inicio, resumo.fim) == (date(2026, 12, 1), date(2026, 12, 4))


def test_rota_segue_o_segmento_e_nao_as_datas() -> None:
    resumo = _resumo(
        classificacaoproduto="Aéreo",
        trechos=[
            fabrica.trecho(2, "GRU", "FCO", "2026-12-01 12:00:00", "2026-12-02 06:00:00"),
            fabrica.trecho(1, "FOR", "GRU", "2026-12-01 06:00:00", "2026-12-01 09:00:00"),
        ],
    )
    assert resumo is not None
    assert resumo.rota == [["FOR", "GRU", "FCO"]]


def test_rota_nao_separa_trechos_com_siglas_ligadas_mesmo_com_dias_de_diferenca() -> None:
    resumo = _resumo(
        classificacaoproduto="Aéreo",
        trechos=[
            fabrica.trecho(1, "FOR", "LIS", "2026-12-01 06:00:00", "2026-12-01 18:00:00"),
            fabrica.trecho(2, "LIS", "FOR", "2026-12-20 06:00:00", "2026-12-20 18:00:00"),
        ],
    )
    assert resumo is not None
    assert resumo.rota == [["FOR", "LIS", "FOR"]]


def test_trecho_sem_sigla_fica_fora_da_rota() -> None:
    resumo = _resumo(
        classificacaoproduto="Aéreo",
        trechos=[
            fabrica.trecho(1, "FOR", "GRU", None, None),
            fabrica.trecho(2, "", "FCO", None, None),
            fabrica.trecho(3, "GRU", "FOR", None, None),
        ],
    )
    assert resumo is not None
    assert resumo.rota == [["FOR", "GRU", "FOR"]]
    assert _resumo(
        classificacaoproduto="Aéreo", trechos=[fabrica.trecho(1, "", "", None, None)]
    ) == (ResumoServico(1, None, None, [], None, None))


def test_resumo_do_servico_diversos() -> None:
    resumo = _resumo(
        classificacaoproduto="Diversos",
        detalheItem=[
            fabrica.servico(descricao="SEGURO X"),
            *[fabrica.servico(descricao=f"OUTRO {i}") for i in range(6)],
        ],
    )
    assert resumo is not None
    assert (resumo.quantidade, resumo.descricao) == (7, "SEGURO X")
    assert resumo.diarias is None


def test_pacote_tem_descricao() -> None:
    resumo = _resumo(
        classificacaoproduto="Pacote", detalheItem=[fabrica.servico(descricao="PACOTE EXEMPLO")]
    )
    assert resumo is not None
    assert resumo.descricao == "PACOTE EXEMPLO"


def test_classificacao_sem_regra_tem_quantidade_e_nada_mais() -> None:
    resumo = _resumo(classificacaoproduto="Outra", detalheItem=[fabrica.servico(descricao="X")])
    assert resumo == ResumoServico(1, None, None, [], None, None)
