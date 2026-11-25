# As datas da AGI são texto local sem fuso: os datetime ingênuos abaixo são o resultado esperado.
# ruff: noqa: DTZ001
from datetime import datetime

import pytest

from stur_api.dominio.datas import ler_data_hora, tem_horario
from stur_api.erros import ApiSturRespostaInvalida


def test_hora_vazia_do_stur_e_none() -> None:
    assert ler_data_hora("1899-12-30T00:00:00") is None
    assert ler_data_hora("2026-05-28 16:43:00") == datetime(2026, 5, 28, 16, 43)


def test_hora_vazia_do_stur_com_espaco_e_none() -> None:
    assert ler_data_hora("1899-12-30 00:00:00") is None


def test_none_e_texto_vazio_viram_none() -> None:
    assert ler_data_hora(None) is None
    assert ler_data_hora("") is None


def test_aceita_t_ou_espaco_como_separador() -> None:
    esperado = datetime(2026, 11, 17, 8, 5, 9)
    assert ler_data_hora("2026-11-17T08:05:09") == esperado
    assert ler_data_hora("2026-11-17 08:05:09") == esperado


def test_data_lida_nao_tem_fuso() -> None:
    lido = ler_data_hora("2026-11-17T08:05:09")
    assert lido is not None and lido.tzinfo is None


def test_tem_horario() -> None:
    assert tem_horario(datetime(2026, 11, 17, 0, 0, 0)) is False
    assert tem_horario(datetime(2026, 11, 17, 0, 0, 1)) is True
    assert tem_horario(datetime(2026, 11, 17, 16, 43)) is True
    assert tem_horario(None) is False


@pytest.mark.parametrize(
    "texto",
    [
        "2026-11-17",  # só data
        "2026-11-17T08:05:09Z",  # sufixo de fuso
        "2026-11-17T08:05:09+00:00",
        "2026-11-17T08:05:09.123",  # fração de segundo
        "20261117T080509",  # formato básico
        "2026-11-17T08:05",  # sem segundos
        "2026-1-7 8:5:9",  # sem zeros à esquerda
        "2026-02-30 00:00:00",  # dia que não existe
        "2026-11-17_08:05:09",  # outro separador
        "17/11/2026 08:05:09",
        "texto-qualquer",
    ],
)
def test_formato_invalido_levanta_erro_sem_o_valor(texto: str) -> None:
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        ler_data_hora(texto, "recebimentos[].dtVencto")
    assert erro.value.codigo == "api_stur_resposta_invalida"
    assert erro.value.detalhe == ["recebimentos[].dtVencto: formato_de_data_invalido"]
    assert texto not in str(erro.value) and texto not in repr(erro.value.detalhe)
    assert erro.value.__suppress_context__ and erro.value.__cause__ is None


def test_campo_padrao_do_detalhe_e_data() -> None:
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        ler_data_hora("2026-11-17")
    assert erro.value.detalhe == ["data: formato_de_data_invalido"]
