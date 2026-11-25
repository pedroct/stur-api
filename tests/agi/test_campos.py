from decimal import Decimal

import pytest

from stur_api.agi.campos import campos_desconhecidos, preenchido, validar_venda
from stur_api.erros import ApiSturRespostaInvalida
from tests import fabrica


def test_modelo_gerado_valida_venda_inventada() -> None:
    venda_agi = validar_venda(fabrica.venda())
    assert venda_agi.idreserva == 1001 and venda_agi.detalheItem[0].vlrTarifaTotal == Decimal(
        "1000.00"
    )


def test_campo_novo_preenchido_e_listado_e_vazio_nao() -> None:
    cru = fabrica.venda(campoNovo="x", outroNovo="")
    cru["detalheItem"][0]["taxaNova"] = Decimal("0")
    assert campos_desconhecidos(cru) == ["campoNovo", "detalheItem[].taxaNova"]


def test_campo_ausente_vira_none() -> None:
    cru = fabrica.venda()
    del cru["nomeEmissor"]
    assert validar_venda(cru).nomeEmissor is None


def test_tipo_errado_e_resposta_invalida_sem_o_valor() -> None:
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        validar_venda(fabrica.venda(idreserva="CLIENTE SECRETO"))
    assert "idreserva" in str(erro.value.detalhe) and "CLIENTE SECRETO" not in str(
        erro.value.detalhe
    )


def test_zero_e_false_contam_como_preenchidos() -> None:
    assert (
        preenchido(Decimal("0")) and preenchido(False) and not preenchido("") and not preenchido({})
    )


def test_erro_em_servico_traz_o_caminho_com_o_indice() -> None:
    cru = fabrica.venda(detalheItem=[fabrica.servico(), fabrica.servico(vlrTarifaTotal="DADO X")])
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        validar_venda(cru)
    assert erro.value.detalhe == ["detalheItem[1].vlrTarifaTotal: decimal_parsing"]


@pytest.mark.parametrize("campo", ["idreserva", "reserva"])
def test_sem_idreserva_ou_reserva_e_resposta_invalida(campo: str) -> None:
    cru = fabrica.venda()
    del cru[campo]
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        validar_venda(cru)
    assert erro.value.detalhe == [f"{campo}: missing"]


def test_fabrica_so_usa_campos_conhecidos() -> None:
    trechos = [fabrica.trecho(1, "FOR", "GIG", "2026-06-10 06:00:00", "2026-06-10 09:20:00")]
    cru = fabrica.venda(trechos=trechos)
    assert campos_desconhecidos(cru) == []
    venda_agi = validar_venda(cru)
    assert venda_agi.trechos[0].origem.sigla == "FOR"
    assert venda_agi.recebimentos[0].valor == Decimal("1050.01")
    assert fabrica.validar_trechos(trechos)[0].destino.sigla == "GIG"
    assert fabrica.validar_servico(fabrica.servico()).vlrCambio == Decimal("1")
