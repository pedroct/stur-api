from datetime import date
from typing import Any

from stur_api.dominio.estado_servico import EstadoServico, estado_do_servico, periodo_do_servico
from tests import fabrica
from tests.fabrica import validar_venda

HOJE = date(2026, 11, 25)


def _estado(**campos: Any) -> EstadoServico | None:
    return estado_do_servico(validar_venda(fabrica.venda(**campos)), HOJE)


def test_hospedagem_concluida() -> None:
    v = validar_venda(
        fabrica.venda(
            classificacaoproduto="Hotelaria",
            detalheItem=[
                fabrica.servico(dtEntrada="2026-11-20 00:00:00", dtSaida="2026-11-22 00:00:00")
            ],
        )
    )
    assert estado_do_servico(v, date(2026, 11, 25)) == EstadoServico(
        "concluido", date(2026, 11, 20), date(2026, 11, 22), "entrada_saida"
    )


def test_hotelaria_usa_a_menor_entrada_e_a_maior_saida() -> None:
    estado = _estado(
        classificacaoproduto="Hotelaria",
        detalheItem=[
            fabrica.servico(dtEntrada="2026-11-28 00:00:00", dtSaida="2026-11-30 00:00:00"),
            fabrica.servico(dtEntrada="2026-11-26 00:00:00", dtSaida="2026-11-29 00:00:00"),
        ],
    )
    assert estado == EstadoServico(
        "a_acontecer", date(2026, 11, 26), date(2026, 11, 30), "entrada_saida"
    )


def test_aereo_usa_primeira_partida_e_ultima_chegada() -> None:
    estado = _estado(
        classificacaoproduto="Aereo",
        trechos=[
            fabrica.trecho(1, "FOR", "GIG", "2026-11-24 06:00:00", "2026-11-24 09:20:00"),
            fabrica.trecho(2, "GIG", "LIS", "2026-11-24 12:30:00", "2026-11-26 01:00:00"),
        ],
    )
    assert estado == EstadoServico(
        "em_andamento", date(2026, 11, 24), date(2026, 11, 26), "trechos"
    )


def test_aereo_com_acento_no_plano_tambem_vale() -> None:
    estado = _estado(
        classificacaoproduto="Aéreo",
        trechos=[fabrica.trecho(1, "FOR", "GIG", "2026-12-01 06:00:00", "2026-12-01 09:20:00")],
    )
    assert estado == EstadoServico("a_acontecer", date(2026, 12, 1), date(2026, 12, 1), "trechos")


def test_rodoviario_sem_chegada_usa_a_partida_como_fim() -> None:
    estado = _estado(
        classificacaoproduto="Rodoviario",
        trechos=[fabrica.trecho(1, "FOR", "REC", "2026-11-10 22:00:00", None)],
    )
    assert estado == EstadoServico("concluido", date(2026, 11, 10), date(2026, 11, 10), "trechos")


def test_locacao_usa_retirada_e_devolucao() -> None:
    estado = _estado(
        classificacaoproduto="Locacao",
        detalheItem=[
            fabrica.servico(dtRetirada="2026-11-20 10:00:00", dtDevolucao="2026-11-30 10:00:00")
        ],
    )
    assert estado == EstadoServico(
        "em_andamento", date(2026, 11, 20), date(2026, 11, 30), "retirada_devolucao"
    )


def test_diversos_usa_inicio_e_termino() -> None:
    estado = _estado(
        classificacaoproduto="Diversos",
        detalheItem=[
            fabrica.servico(dtInicio="2026-12-05 00:00:00", dtTermino="2026-12-07 00:00:00")
        ],
    )
    assert estado == EstadoServico(
        "a_acontecer", date(2026, 12, 5), date(2026, 12, 7), "inicio_termino"
    )


def test_pacote_usa_inicio_e_termino() -> None:
    estado = _estado(
        classificacaoproduto="Pacote",
        detalheItem=[
            fabrica.servico(dtInicio="2026-10-05 00:00:00", dtTermino="2026-10-07 00:00:00")
        ],
    )
    assert estado == EstadoServico(
        "concluido", date(2026, 10, 5), date(2026, 10, 7), "inicio_termino"
    )


def test_cancelada_nao_tem_estado() -> None:
    estado = _estado(
        status="CANCELADA",
        classificacaoproduto="Diversos",
        detalheItem=[
            fabrica.servico(dtInicio="2026-11-20 00:00:00", dtTermino="2026-11-30 00:00:00")
        ],
    )
    assert estado is None


def test_em_andamento_no_dia_do_inicio_e_no_dia_do_fim() -> None:
    servico = fabrica.servico(dtInicio="2026-11-25 14:00:00", dtTermino="2026-11-25 18:00:00")
    estado = _estado(classificacaoproduto="Diversos", detalheItem=[servico])
    assert estado == EstadoServico("em_andamento", HOJE, HOJE, "inicio_termino")
    venda = validar_venda(fabrica.venda(classificacaoproduto="Diversos", detalheItem=[servico]))
    assert estado_do_servico(venda, date(2026, 11, 26)) == EstadoServico(
        "concluido", HOJE, HOJE, "inicio_termino"
    )


def test_sem_datas_nao_tem_estado() -> None:
    assert _estado(classificacaoproduto="Hotelaria") is None
    assert _estado(classificacaoproduto="Aereo", trechos=[]) is None
    assert (
        _estado(
            classificacaoproduto="Aereo",
            trechos=[fabrica.trecho(1, "FOR", "GIG", None, "1899-12-30 00:00:00")],
        )
        is None
    )


def test_data_vazia_de_um_lado_so_nao_tem_estado() -> None:
    estado = _estado(
        classificacaoproduto="Hotelaria",
        detalheItem=[fabrica.servico(dtEntrada="2026-11-20 00:00:00", dtSaida=None)],
    )
    assert estado is None


def test_classificacao_desconhecida_nao_tem_estado() -> None:
    estado = _estado(
        classificacaoproduto="Seguro",
        detalheItem=[
            fabrica.servico(dtInicio="2026-11-20 00:00:00", dtTermino="2026-11-30 00:00:00")
        ],
    )
    assert estado is None


def test_periodo_do_servico_vale_na_cancelada() -> None:
    venda = validar_venda(
        fabrica.venda(
            status="CANCELADA",
            classificacaoproduto="Hotelaria",
            detalheItem=[
                fabrica.servico(dtEntrada="2026-11-26 00:00:00", dtSaida="2026-11-28 00:00:00")
            ],
        )
    )
    assert periodo_do_servico(venda) == (date(2026, 11, 26), date(2026, 11, 28))
    assert estado_do_servico(venda, HOJE) is None


def test_periodo_do_servico_sem_regra_e_sem_datas() -> None:
    sem_regra = validar_venda(fabrica.venda(classificacaoproduto="Outra"))
    assert periodo_do_servico(sem_regra) == (None, None)
    sem_datas = validar_venda(fabrica.venda(classificacaoproduto="Hotelaria"))
    assert periodo_do_servico(sem_datas) == (None, None)
