from datetime import date

import pytest

from stur_api.config import Configuracao
from stur_api.dominio.consulta import ConsultaVendas, TipoData, filtro_agi, validar_consulta
from stur_api.erros import ConsultaInvalida


def test_mensagens_da_validacao(config: Configuracao) -> None:
    casos = [
        (ConsultaVendas(None, de=None, ate=None), "consulta_vazia", "reserva"),
        (ConsultaVendas(None, de=date(2026, 11, 1), ate=None), "periodo_incompleto", "ate"),
        (ConsultaVendas(None, de=None, ate=date(2026, 11, 1)), "periodo_incompleto", "de"),
        (
            ConsultaVendas(None, de=date(2026, 11, 2), ate=date(2026, 11, 1)),
            "periodo_invertido",
            "ate",
        ),
        (
            ConsultaVendas(None, de=date(2026, 10, 1), ate=date(2026, 11, 1)),
            "periodo_longo",
            "de",
        ),
    ]
    for consulta, codigo, campo in casos:
        with pytest.raises(ConsultaInvalida) as erro:
            validar_consulta(consulta, config)
        assert (erro.value.codigo, erro.value.campo) == (codigo, campo)


def test_textos_das_mensagens(config: Configuracao) -> None:
    textos = {
        ConsultaVendas(None): "Digite o número da reserva, escolha um período ou os dois.",
        ConsultaVendas(None, de=date(2026, 11, 1)): "Preencha as duas datas do período.",
        ConsultaVendas(None, de=date(2026, 11, 2), ate=date(2026, 11, 1)): (
            "A data final é anterior à inicial."
        ),
        ConsultaVendas(None, de=date(2026, 10, 1), ate=date(2026, 11, 1)): (
            "Sem número de reserva, o período vai até 31 dias. "
            "Diminua o período ou informe o número."
        ),
    }
    for consulta, mensagem in textos.items():
        with pytest.raises(ConsultaInvalida) as erro:
            validar_consulta(consulta, config)
        assert erro.value.mensagem == mensagem


def test_mensagem_do_periodo_longo_usa_o_parametro(config: Configuracao) -> None:
    config = config.model_copy(update={"periodo_maximo_dias": 10})
    consulta = ConsultaVendas(None, de=date(2026, 10, 1), ate=date(2026, 10, 11))
    with pytest.raises(ConsultaInvalida) as erro:
        validar_consulta(consulta, config)
    assert erro.value.mensagem == (
        "Sem número de reserva, o período vai até 10 dias. Diminua o período ou informe o número."
    )
    validar_consulta(ConsultaVendas(None, de=date(2026, 10, 1), ate=date(2026, 10, 10)), config)


def test_31_dias_passa_e_32_nao(config: Configuracao) -> None:
    validar_consulta(ConsultaVendas(None, de=date(2026, 10, 1), ate=date(2026, 10, 31)), config)
    consulta = ConsultaVendas(None, de=date(2026, 10, 1), ate=date(2026, 11, 1))
    with pytest.raises(ConsultaInvalida) as erro:
        validar_consulta(consulta, config)
    assert erro.value.codigo == "periodo_longo"


def test_com_numero_o_periodo_pode_ser_longo(config: Configuracao) -> None:
    validar_consulta(ConsultaVendas(90000001, de=date(2026, 1, 1), ate=date(2026, 11, 1)), config)
    validar_consulta(ConsultaVendas(90000001), config)


def test_com_numero_ainda_valida_periodo_incompleto_e_invertido(config: Configuracao) -> None:
    incompleta = ConsultaVendas(90000001, de=date(2026, 11, 1))
    with pytest.raises(ConsultaInvalida) as erro:
        validar_consulta(incompleta, config)
    assert erro.value.codigo == "periodo_incompleto"
    invertida = ConsultaVendas(90000001, de=date(2026, 11, 2), ate=date(2026, 11, 1))
    with pytest.raises(ConsultaInvalida) as erro:
        validar_consulta(invertida, config)
    assert erro.value.codigo == "periodo_invertido"


def test_consulta_e_hashavel() -> None:
    a = ConsultaVendas(
        None, de=date(2026, 11, 1), ate=date(2026, 11, 2), situacoes=frozenset({"fechada"})
    )
    b = ConsultaVendas(
        None, de=date(2026, 11, 1), ate=date(2026, 11, 2), situacoes=frozenset({"fechada"})
    )
    assert hash(a) == hash(b)
    assert a == b


def test_so_numero_usa_a_janela_larga(config: Configuracao) -> None:
    f = filtro_agi(ConsultaVendas(90000001, de=None, ate=None), config, date(2026, 11, 25))
    assert (f.tipo_data, f.data_inicial, f.data_final, f.reserva) == (
        "EMISSAO",
        date(2020, 1, 1),
        date(2027, 12, 31),
        90000001,
    )


def test_so_numero_ignora_o_tipo_de_data(config: Configuracao) -> None:
    f = filtro_agi(ConsultaVendas(90000001, tipo_data="alteracao"), config, date(2026, 11, 25))
    assert f.tipo_data == "EMISSAO"


def test_periodo_usa_o_tipo_de_data_em_maiusculas(config: Configuracao) -> None:
    casos: list[tuple[TipoData, str]] = [
        ("emissao", "EMISSAO"),
        ("confirmacao", "CONFIRMACAO"),
        ("alteracao", "ALTERACAO"),
    ]
    for tipo, esperado in casos:
        c = ConsultaVendas(None, tipo_data=tipo, de=date(2026, 11, 1), ate=date(2026, 11, 5))
        f = filtro_agi(c, config, date(2026, 11, 25))
        assert (f.tipo_data, f.data_inicial, f.data_final, f.reserva) == (
            esperado,
            date(2026, 11, 1),
            date(2026, 11, 5),
            None,
        )


def test_status_vai_a_agi_so_com_uma_situacao(config: Configuracao) -> None:
    hoje = date(2026, 11, 25)
    de, ate = date(2026, 11, 1), date(2026, 11, 5)
    uma = ConsultaVendas(None, situacoes=frozenset({"cancelada"}), de=de, ate=ate)
    duas = ConsultaVendas(None, situacoes=frozenset({"cancelada", "fechada"}), de=de, ate=ate)
    nenhuma = ConsultaVendas(None, de=de, ate=ate)
    assert filtro_agi(uma, config, hoje).status == "CANCELADA"
    assert filtro_agi(duas, config, hoje).status is None
    assert filtro_agi(nenhuma, config, hoje).status is None


def test_itens_por_pagina(config: Configuracao) -> None:
    hoje = date(2026, 11, 25)
    periodo = ConsultaVendas(None, de=date(2026, 11, 1), ate=date(2026, 11, 5))
    assert filtro_agi(periodo, config, hoje).itens_por_pagina == config.agi_itens_por_pagina
    assert filtro_agi(ConsultaVendas(90000001), config, hoje).itens_por_pagina == 100
