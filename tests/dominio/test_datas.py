# As datas da AGI são texto local sem fuso: os datetime ingênuos abaixo são o resultado esperado.
# ruff: noqa: DTZ001
from datetime import datetime

from stur_api.dominio.datas import ler_data_hora, tem_horario


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
