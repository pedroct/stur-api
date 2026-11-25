import pytest

from stur_api.dominio.itinerario import Espera, Estadia, Trajeto, montar_itinerario
from stur_api.erros import ApiSturRespostaInvalida
from tests import fabrica
from tests.fabrica import validar_trechos


def test_sem_trechos_nao_tem_itinerario() -> None:
    assert montar_itinerario([], 24) is None


def test_espera_no_mesmo_aeroporto_com_mesmo_localizador() -> None:
    t = [
        fabrica.trecho(
            1,
            "FOR",
            "GIG",
            "2026-06-10 06:00:00",
            "2026-06-10 09:20:00",
            localizador="ABC123",
            voo="1",
        ),
        fabrica.trecho(
            2,
            "GIG",
            "LIS",
            "2026-06-10 12:30:00",
            "2026-06-11 01:00:00",
            localizador="ABC123",
            voo="2",
        ),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.forma == "com_horario" and it.trajetos == [Trajeto([0, 1], [Espera(0, 190, "GIG")])]
    assert it.estadias == []


def test_sem_horario_nao_calcula_espera_e_e_so_datas() -> None:
    t = [
        fabrica.trecho(
            1, "FOR", "GIG", "2026-06-10 00:00:00", "2026-06-10 00:00:00", localizador="ABC123"
        ),
        fabrica.trecho(
            2, "GIG", "LIS", "2026-06-10 00:00:00", "2026-06-11 00:00:00", localizador="ABC123"
        ),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.forma == "so_datas"
    assert it.trajetos == [Trajeto([0, 1], [])]


def test_um_horario_so_nao_basta_para_a_espera() -> None:
    # a chegada do primeiro trecho vem sem hora: a forma tem horário, mas a espera não se calcula
    t = [
        fabrica.trecho(
            1, "FOR", "GIG", "2026-06-10 06:00:00", "2026-06-10 00:00:00", localizador="ABC123"
        ),
        fabrica.trecho(
            2, "GIG", "LIS", "2026-06-10 12:30:00", "2026-06-11 01:00:00", localizador="ABC123"
        ),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.forma == "com_horario"
    assert it.trajetos == [Trajeto([0, 1], [])]


def test_sem_data_e_sem_dados() -> None:
    t = [
        fabrica.trecho(1, "FOR", "GIG", None, None, localizador="ABC123"),
        fabrica.trecho(2, "GIG", "LIS", "1899-12-30 00:00:00", None, localizador="ABC123"),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.forma == "sem_dados"
    # sem as duas datas não há como ligar um trecho ao outro: um trajeto por trecho
    assert it.trajetos == [Trajeto([0], []), Trajeto([1], [])]
    assert it.estadias == []


def test_falta_a_data_de_um_dos_dois_comeca_trajeto() -> None:
    t = [
        fabrica.trecho(
            1, "FOR", "GIG", "2026-06-10 06:00:00", "2026-06-10 09:20:00", localizador="A"
        ),
        fabrica.trecho(2, "GIG", "LIS", None, "2026-06-11 01:00:00", localizador="A"),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.trajetos == [Trajeto([0], []), Trajeto([1], [])]
    assert it.estadias == []


def test_localizador_vazio_nao_calcula_espera() -> None:
    t = [
        fabrica.trecho(1, "FOR", "GIG", "2026-06-10 06:00:00", "2026-06-10 09:20:00", voo="1"),
        fabrica.trecho(2, "GIG", "LIS", "2026-06-10 12:30:00", "2026-06-11 01:00:00", voo="2"),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.forma == "com_horario"
    assert it.trajetos == [Trajeto([0, 1], [])]


def test_localizadores_diferentes_nao_calculam_espera() -> None:
    t = [
        fabrica.trecho(
            1, "FOR", "GIG", "2026-06-10 06:00:00", "2026-06-10 09:20:00", localizador="AAA111"
        ),
        fabrica.trecho(
            2, "GIG", "LIS", "2026-06-10 12:30:00", "2026-06-11 01:00:00", localizador="BBB222"
        ),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.trajetos == [Trajeto([0, 1], [])]


def test_outro_aeroporto_comeca_trajeto() -> None:
    t = [
        fabrica.trecho(
            1, "FOR", "GIG", "2026-06-10 06:00:00", "2026-06-10 09:20:00", localizador="A"
        ),
        fabrica.trecho(
            2, "SDU", "LIS", "2026-06-10 12:30:00", "2026-06-11 01:00:00", localizador="A"
        ),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.trajetos == [Trajeto([0], []), Trajeto([1], [])]
    assert it.estadias == [Estadia(0, 0, "GIG", None)]


def test_estadia_entre_trajetos() -> None:
    t = [
        fabrica.trecho(
            1, "FOR", "FCO", "2026-06-10 20:00:00", "2026-06-11 11:00:00", destino_cidade="ROMA"
        ),
        fabrica.trecho(
            2, "FCO", "FOR", "2026-06-19 13:00:00", "2026-06-19 23:00:00", origem_cidade="ROMA"
        ),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.trajetos == [Trajeto([0], []), Trajeto([1], [])]
    assert it.estadias == [Estadia(0, 8, "FCO", "ROMA")]


def test_partida_depois_do_corte_comeca_trajeto_mesmo_no_mesmo_aeroporto() -> None:
    t = [
        fabrica.trecho(
            1, "FOR", "GIG", "2026-06-10 06:00:00", "2026-06-10 09:20:00", localizador="A"
        ),
        fabrica.trecho(
            2, "GIG", "LIS", "2026-06-11 09:20:00", "2026-06-12 01:00:00", localizador="A"
        ),
    ]
    # exatamente 24 h depois da chegada: já é trajeto novo
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    assert it.trajetos == [Trajeto([0], []), Trajeto([1], [])]
    assert it.estadias == [Estadia(0, 1, "GIG", None)]
    # com o corte maior, os dois ficam no mesmo trajeto, com a espera de 24 h
    it = montar_itinerario(validar_trechos(t), 48)
    assert it is not None
    assert it.trajetos == [Trajeto([0, 1], [Espera(0, 1440, "GIG")])]


def test_ordena_por_segmento() -> None:
    t = [
        fabrica.trecho(
            2, "GIG", "LIS", "2026-06-10 12:30:00", "2026-06-11 01:00:00", localizador="A"
        ),
        fabrica.trecho(
            1, "FOR", "GIG", "2026-06-10 06:00:00", "2026-06-10 09:20:00", localizador="A"
        ),
    ]
    it = montar_itinerario(validar_trechos(t), 24)
    assert it is not None
    # os índices continuam sendo os da lista da API; a ordem é a do segmento
    assert it.trajetos == [Trajeto([1, 0], [Espera(1, 190, "GIG")])]


def test_data_em_formato_desconhecido_e_erro_com_o_campo() -> None:
    t = [fabrica.trecho(1, "FOR", "GIG", "10/06/2026", None)]
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        montar_itinerario(validar_trechos(t), 24)
    assert erro.value.detalhe == ["trechos[].dtPartida: formato_de_data_invalido"]
