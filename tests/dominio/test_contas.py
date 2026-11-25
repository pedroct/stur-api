from decimal import Decimal
from typing import Any

import pytest

from stur_api.config import Configuracao
from stur_api.dominio.contas import (
    ContaServico,
    Conversao,
    conta_do_servico,
    percentual_lucro,
    verificar_totais,
)
from tests import fabrica
from tests.fabrica import validar_servico, validar_venda

D = Decimal


def _contas(venda: dict[str, Any], situacao: str = "FECHADA") -> list[ContaServico]:
    return [
        conta_do_servico(validar_servico(s), i, situacao)
        for i, s in enumerate(venda["detalheItem"], start=1)
    ]


def _servico_convertido(**campos: Any) -> dict[str, Any]:
    """EUR a câmbio 2: tarifa de 10 vira 20 no cliente; o fornecedor fica em real."""
    return fabrica.servico(
        vlrTarifaTotal=D("10.00"), siglaMoedaTarifa="EUR", vlrCambio=D("2.00"), **campos
    )


def test_conta_do_cliente_em_real() -> None:
    s = fabrica.servico(
        vlrTarifaTotal=D("1000.00"),
        vlrTaxas=D("100.00"),
        vlrTxServico=D("0.01"),
        vlrDesconto=D("50.00"),
    )
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert conta.cliente.total == D("1050.01")
    assert [t.campo for t in conta.cliente.termos] == [
        "vlrTarifaTotal",
        "vlrTaxas",
        "vlrTxServico",
        "vlrDesconto",
    ]
    assert conta.cliente.termos[-1].efeito == "reduz" and "vlrTxExt" in conta.cliente.zerados


def test_conta_do_fornecedor_reduz_acordo_over_e_comissao() -> None:
    s = fabrica.servico(
        vlrTarifaTotalp=D("900"),
        vlrTaxasP=D("90"),
        vlrFeePagar=D("10"),
        vlrDescontoAcordo=D("5"),
        vlrOverRec=D("3"),
        vlrComisRecebida=D("45"),
    )
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert conta.fornecedor.total == D("947")
    assert [(t.campo, t.efeito) for t in conta.fornecedor.termos] == [
        ("vlrTarifaTotalp", "soma"),
        ("vlrTaxasP", "soma"),
        ("vlrFeePagar", "soma"),
        ("vlrDescontoAcordo", "reduz"),
        ("vlrOverRec", "reduz"),
        ("vlrComisRecebida", "reduz"),
    ]
    assert conta.fornecedor.zerados == ["vlrTxExtP", "vlrTxEmbp"]


def test_ordem_dos_termos_do_cliente_e_do_fornecedor() -> None:
    s = fabrica.servico(
        **{
            c: D("1")
            for c in [
                "vlrTarifaTotal",
                "vlrTaxas",
                "vlrTxExt",
                "vlrTxServico",
                "vlrTxEmb",
                "vlrTxDU",
                "vlrDesconto",
                "vlrTarifaTotalp",
                "vlrTaxasP",
                "vlrTxExtP",
                "vlrTxEmbp",
                "vlrFeePagar",
                "vlrDescontoAcordo",
                "vlrOverRec",
                "vlrComisRecebida",
            ]
        }
    )
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert [t.campo for t in conta.cliente.termos] == [
        "vlrTarifaTotal",
        "vlrTaxas",
        "vlrTxExt",
        "vlrTxServico",
        "vlrTxEmb",
        "vlrTxDU",
        "vlrDesconto",
    ]
    assert [t.campo for t in conta.fornecedor.termos] == [
        "vlrTarifaTotalp",
        "vlrTaxasP",
        "vlrTxExtP",
        "vlrTxEmbp",
        "vlrFeePagar",
        "vlrDescontoAcordo",
        "vlrOverRec",
        "vlrComisRecebida",
    ]
    assert conta.cliente.zerados == [] and conta.fornecedor.zerados == []
    assert conta.cliente.total == D("5") and conta.fornecedor.total == D("2")


def test_tarifa_zerada_continua_nos_termos_e_campo_none_conta_como_zero() -> None:
    s = fabrica.servico(vlrTaxas=D("7.50"), vlrTxExt=None)
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert [t.campo for t in conta.cliente.termos] == ["vlrTarifaTotal", "vlrTaxas"]
    assert conta.cliente.termos[0].valor == D("0")
    assert "vlrTarifaTotal" not in conta.cliente.zerados
    assert "vlrTxExt" in conta.cliente.zerados
    assert [t.campo for t in conta.fornecedor.termos] == ["vlrTarifaTotalp"]
    assert conta.cliente.total == D("7.50")


def test_so_a_tarifa_e_convertida() -> None:
    s = fabrica.servico(
        vlrTarifaTotal=D("100.00"), siglaMoedaTarifa="EUR", vlrCambio=D("6.03"), vlrTaxas=D("10.00")
    )
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert conta.cliente.total == D("613.00")
    assert conta.cliente.conversao == Conversao("EUR", D("100.00"), D("6.03"), None)
    assert conta.fornecedor.conversao is None


def test_conversao_guarda_a_data_do_cambio() -> None:
    s = fabrica.servico(
        vlrTarifaTotal=D("100.00"),
        siglaMoedaTarifa="EUR",
        vlrCambio=D("6.03"),
        dtCambio="2026-11-20 00:00:00",
    )
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert conta.cliente.conversao == Conversao(
        "EUR", D("100.00"), D("6.03"), "2026-11-20 00:00:00"
    )


def test_conversao_do_fornecedor_usa_os_campos_com_p() -> None:
    s = fabrica.servico(
        vlrTarifaTotalp=D("80.00"),
        siglaMoedaTarifap="US$",
        vlrCambiop=D("5.50"),
        dtCambiop="2026-11-21 00:00:00",
        vlrTaxasP=D("2.00"),
    )
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert conta.fornecedor.total == D("442.00")
    assert conta.fornecedor.conversao == Conversao(
        "US$", D("80.00"), D("5.50"), "2026-11-21 00:00:00"
    )
    assert conta.cliente.conversao is None


@pytest.mark.parametrize("sigla", ["R$", "BRL"])
def test_real_nunca_converte_mesmo_com_cambio_diferente_de_1(sigla: str) -> None:
    s = fabrica.servico(vlrTarifaTotal=D("100.00"), siglaMoedaTarifa=sigla, vlrCambio=D("2"))
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert conta.cliente.conversao is None and conta.cliente.sigla_com_cambio_1 is None


def test_sigla_estrangeira_com_cambio_1_nao_converte() -> None:
    s = fabrica.servico(vlrTarifaTotal=D("8244.88"), siglaMoedaTarifa="US$", vlrCambio=D("1.0000"))
    conta = conta_do_servico(validar_servico(s), 1, "FECHADA")
    assert (
        conta.cliente.total == D("8244.88")
        and conta.cliente.conversao is None
        and conta.cliente.sigla_com_cambio_1 == "US$"
    )


def test_margem_e_percentual_do_servico() -> None:
    s = fabrica.servico(vlrTarifaTotal=D("1000.00"), vlrTarifaTotalp=D("900.00"))
    conta = conta_do_servico(validar_servico(s), 3, "FECHADA")
    assert conta.indice == 3
    assert conta.margem == D("100.00")
    assert conta.percentual_lucro == D("10.00")
    vazio = conta_do_servico(validar_servico(fabrica.servico()), 1, "FECHADA")
    assert vazio.margem == D("0") and vazio.percentual_lucro is None


def test_percentual_com_total_zero_nao_se_aplica() -> None:
    assert percentual_lucro(D("3698.14"), D("0")) is None
    assert percentual_lucro(D("24319.98"), D("150197.72")) == D("16.19")


def test_percentual_arredonda_meio_para_cima() -> None:
    assert percentual_lucro(D("1.005"), D("100")) == D("1.01")
    assert percentual_lucro(D("-1"), D("8")) == D("-12.50")


def test_comissao_zerada_em_confirmada_e_nao_apurada() -> None:
    s = validar_servico(fabrica.servico())
    assert conta_do_servico(s, 1, "CONFIRMADA").comissoes_nao_apuradas is True
    assert conta_do_servico(s, 1, "FECHADA").comissoes_nao_apuradas is False
    assert conta_do_servico(s, 1, "fechada").comissoes_nao_apuradas is False
    com_emissor = validar_servico(fabrica.servico(vlrComissaoEmissor=D("10")))
    assert conta_do_servico(com_emissor, 1, "CONFIRMADA").comissoes_nao_apuradas is False
    com_promotor = validar_servico(fabrica.servico(vlrComissaoPromotor=D("10")))
    assert conta_do_servico(com_promotor, 1, "CONFIRMADA").comissoes_nao_apuradas is False
    ausente = validar_servico(fabrica.servico(vlrComissaoEmissor=None, vlrComissaoPromotor=None))
    assert conta_do_servico(ausente, 1, "CONFIRMADA").comissoes_nao_apuradas is True


def test_venda_padrao_fecha(config: Configuracao) -> None:
    venda = fabrica.venda()
    v = verificar_totais(validar_venda(venda), _contas(venda), config)
    assert v.fecha is True and v.tolerancia == D("0.02")
    assert [c.conta for c in v.contas] == ["cliente", "fornecedor", "margem"]
    assert [c.diferenca for c in v.contas] == [D("0"), D("0"), D("0")]


def test_verificacao_fecha_dentro_da_tolerancia(config: Configuracao) -> None:
    # diferença de 0,02 → fecha
    venda = fabrica.venda(totalCliente=D("1050.03"), margemLucroBruta=D("60.03"))
    v = verificar_totais(validar_venda(venda), _contas(venda), config)
    cliente = v.contas[0]
    assert cliente.calculado == D("1050.01") and cliente.api == D("1050.03")
    assert cliente.diferenca == D("-0.02") and cliente.fecha is True
    assert v.fecha is True
    # 0,03 já passa da tolerância
    venda = fabrica.venda(totalCliente=D("1050.04"), margemLucroBruta=D("60.04"))
    v = verificar_totais(validar_venda(venda), _contas(venda), config)
    assert v.contas[0].fecha is False and v.fecha is False


def test_verificacao_nao_fecha_e_diz_quanto(config: Configuracao) -> None:
    # Σ cliente 1050,01 e totalCliente 1060,01 → diferenca −10,00 na conta "cliente"
    venda = fabrica.venda(totalCliente=D("1060.01"))
    v = verificar_totais(validar_venda(venda), _contas(venda), config)
    por_conta = {c.conta: c for c in v.contas}
    assert por_conta["cliente"].calculado == D("1050.01")
    assert por_conta["cliente"].api == D("1060.01")
    assert por_conta["cliente"].diferenca == D("-10.00")
    assert por_conta["cliente"].fecha is False
    assert por_conta["fornecedor"].fecha is True
    assert por_conta["margem"].fecha is True
    assert v.fecha is False


def test_margem_e_fornecedor_tambem_derrubam_a_verificacao(config: Configuracao) -> None:
    venda = fabrica.venda(totalFornecedor=D("991.00"), margemLucroBruta=D("70.00"))
    v = verificar_totais(validar_venda(venda), _contas(venda), config)
    por_conta = {c.conta: c for c in v.contas}
    assert por_conta["fornecedor"].diferenca == D("-1.00")
    assert por_conta["margem"].calculado == D("60.01") and por_conta["margem"].api == D("70.00")
    assert por_conta["margem"].diferenca == D("-9.99")
    assert v.fecha is False


def test_totais_ausentes_na_venda_contam_como_zero(config: Configuracao) -> None:
    venda = fabrica.venda(totalCliente=None)
    v = verificar_totais(validar_venda(venda), _contas(venda), config)
    assert v.contas[0].api == D("0") and v.contas[0].diferenca == D("1050.01")


def test_soma_os_servicos_da_venda(config: Configuracao) -> None:
    venda = fabrica.venda(
        totalCliente=D("30.00"),
        totalFornecedor=D("12.00"),
        margemLucroBruta=D("18.00"),
        detalheItem=[
            fabrica.servico(vlrTarifaTotal=D("10.00"), vlrTarifaTotalp=D("4.00")),
            fabrica.servico(vlrTarifaTotal=D("20.00"), vlrTarifaTotalp=D("8.00")),
        ],
    )
    v = verificar_totais(validar_venda(venda), _contas(venda), config)
    assert [c.calculado for c in v.contas] == [D("30.00"), D("12.00"), D("18.00")]
    assert v.fecha is True


def test_tolerancia_cresce_com_servicos_convertidos(config: Configuracao) -> None:
    # 3 convertidos → 0,15
    venda = fabrica.venda(
        totalCliente=D("60.15"),
        totalFornecedor=D("0"),
        margemLucroBruta=D("60.00"),
        detalheItem=[_servico_convertido(), _servico_convertido(), _servico_convertido()],
    )
    v = verificar_totais(validar_venda(venda), _contas(venda), config)
    assert v.tolerancia == D("0.15")
    assert v.contas[0].diferenca == D("-0.15") and v.contas[0].fecha is True
    assert v.fecha is True
    fora = fabrica.venda(**{**venda, "totalCliente": D("60.16")})
    assert verificar_totais(validar_venda(fora), _contas(fora), config).fecha is False


def test_tolerancia_sem_servico_convertido_e_a_do_real(config: Configuracao) -> None:
    venda = fabrica.venda()
    assert verificar_totais(validar_venda(venda), _contas(venda), config).tolerancia == D("0.02")


def test_tolerancia_com_um_convertido_nao_cai_abaixo_da_do_real(config: Configuracao) -> None:
    venda = fabrica.venda(
        totalCliente=D("20.00"),
        totalFornecedor=D("0"),
        margemLucroBruta=D("20.00"),
        detalheItem=[_servico_convertido()],
    )
    assert verificar_totais(validar_venda(venda), _contas(venda), config).tolerancia == D("0.05")
    alta = config.model_copy(update={"tolerancia_real": D("0.10")})
    assert verificar_totais(validar_venda(venda), _contas(venda), alta).tolerancia == D("0.10")


def test_servico_convertido_dos_dois_lados_conta_uma_vez(config: Configuracao) -> None:
    ambos = _servico_convertido(
        vlrTarifaTotalp=D("5.00"), siglaMoedaTarifap="EUR", vlrCambiop=D("2.00")
    )
    venda = fabrica.venda(
        totalCliente=D("20.00"),
        totalFornecedor=D("10.00"),
        margemLucroBruta=D("10.00"),
        detalheItem=[ambos, fabrica.servico()],
    )
    assert verificar_totais(validar_venda(venda), _contas(venda), config).tolerancia == D("0.05")
