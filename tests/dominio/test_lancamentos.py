from datetime import date
from decimal import Decimal

from stur_api.dominio.lancamentos import (
    situacao_dos_pagamentos,
    situacao_dos_recebimentos,
    total_dos_pagamentos,
)
from tests import fabrica
from tests.fabrica import validar_venda

D = Decimal
HOJE = date(2026, 11, 25)


def test_em_aberto_e_vencido() -> None:
    v = validar_venda(
        fabrica.venda(
            totalAReceberCliente=D("924.01"),
            totalRecebidoCliente=D("0"),
            recebimentos=[
                fabrica.recebimento(valor=D("224.00"), dtVencto="2026-11-17 00:00:00"),
                fabrica.recebimento(valor=D("700.01"), dtVencto="2026-12-07 00:00:00"),
            ],
        )
    )
    r = situacao_dos_recebimentos(v, HOJE)
    assert [(x.situacao, x.vencido) for x in r] == [("em_aberto", True), ("em_aberto", False)]
    assert [x.indice for x in r] == [0, 1]


def test_vence_hoje_ainda_nao_esta_vencido_e_sem_data_nao_vence() -> None:
    v = validar_venda(
        fabrica.venda(
            totalAReceberCliente=D("300.00"),
            totalRecebidoCliente=D("0"),
            recebimentos=[
                fabrica.recebimento(valor=D("100.00"), dtVencto="2026-11-25 00:00:00"),
                fabrica.recebimento(valor=D("100.00"), dtVencto="1899-12-30 00:00:00"),
                fabrica.recebimento(valor=D("100.00"), dtVencto=None),
            ],
        )
    )
    r = situacao_dos_recebimentos(v, HOJE)
    assert [(x.situacao, x.vencido) for x in r] == [("em_aberto", False)] * 3


def test_reservada_e_sempre_previsto() -> None:
    v = validar_venda(
        fabrica.venda(
            status="RESERVADA",
            totalAReceberCliente=D("924.01"),
            totalRecebidoCliente=D("0"),
            totalAPagarFornec=D("500.00"),
            totalPagoFornec=D("0"),
            recebimentos=[fabrica.recebimento(dtVencto="2026-11-17 00:00:00")],
            pagamentos=[
                fabrica.pagamento(dtVencto="2026-11-17 00:00:00"),
                fabrica.pagamento(forma=2, valor=D("10.00"), dtVencto="2026-11-17 00:00:00"),
            ],
        )
    )
    for lista in (situacao_dos_recebimentos(v, HOJE), situacao_dos_pagamentos(v, HOJE)):
        assert lista
        assert all(x.situacao == "previsto" and x.vencido is False for x in lista)


def test_sem_saldo_quando_nada_a_receber() -> None:
    v = validar_venda(
        fabrica.venda(
            totalAReceberCliente=D("0.00"),
            totalRecebidoCliente=D("1050.01"),
            recebimentos=[fabrica.recebimento(dtVencto="2026-11-17 00:00:00")],
        )
    )
    r = situacao_dos_recebimentos(v, HOJE)
    assert [(x.situacao, x.vencido) for x in r] == [("sem_saldo", False)]


def test_campos_ausentes_contam_como_zero() -> None:
    v = validar_venda(
        fabrica.venda(totalAReceberCliente=None, totalRecebidoCliente=None, recebimentos=None)
    )
    assert situacao_dos_recebimentos(v, HOJE) == []


def test_recebido_em_parte() -> None:
    v = validar_venda(
        fabrica.venda(
            totalAReceberCliente=D("424.01"),
            totalRecebidoCliente=D("500.00"),
            recebimentos=[fabrica.recebimento(dtVencto="2026-11-17 00:00:00")],
        )
    )
    r = situacao_dos_recebimentos(v, HOJE)
    assert [(x.situacao, x.vencido) for x in r] == [("recebido_em_parte", False)]


def test_cartao_repassado_vem_do_recebimento() -> None:
    v = validar_venda(
        fabrica.venda(
            recebimentos=[
                fabrica.recebimento(forma=2, cartaoRepassadoAoFornecedor=True),
                fabrica.recebimento(forma=1, cartaoRepassadoAoFornecedor=False),
                fabrica.recebimento(forma=1, cartaoRepassadoAoFornecedor=None),
            ]
        )
    )
    assert [x.cartao_repassado for x in situacao_dos_recebimentos(v, HOJE)] == [True, False, False]
    assert situacao_dos_recebimentos(v, HOJE)[0].valor_exibido == D("1050.01")


def test_pagamentos_usam_a_pagar_e_pago_do_fornecedor() -> None:
    v = validar_venda(
        fabrica.venda(
            totalAPagarFornec=D("300.00"),
            totalPagoFornec=D("0"),
            pagamentos=[
                fabrica.pagamento(dtVencto="2026-11-20 00:00:00"),
                fabrica.pagamento(dtVencto="2026-12-20 00:00:00"),
            ],
        )
    )
    p = situacao_dos_pagamentos(v, HOJE)
    assert [(x.situacao, x.vencido, x.cartao_repassado) for x in p] == [
        ("em_aberto", True, False),
        ("em_aberto", False, False),
    ]
    v = validar_venda(fabrica.venda(totalAPagarFornec=D("100.00"), totalPagoFornec=D("890.00")))
    assert situacao_dos_pagamentos(v, HOJE)[0].situacao == "recebido_em_parte"


def test_credito_aparece_negativo_e_abate_o_total() -> None:
    v = validar_venda(
        fabrica.venda(
            totalAReceberFornecedor=D("13620.74"),
            pagamentos=[
                fabrica.pagamento(forma=0, valor=D("139498.48")),
                fabrica.pagamento(forma=2, valor=D("13620.74")),
            ],
        )
    )
    p = situacao_dos_pagamentos(v, HOJE)
    assert p[1].valor_exibido == D("-13620.74") and p[1].eh_credito and p[1].situacao == "em_aberto"
    assert not p[0].eh_credito and p[0].valor_exibido == D("139498.48")
    assert total_dos_pagamentos(v) == D("125877.74")


def test_credito_usa_a_receber_e_recebido_do_fornecedor() -> None:
    v = validar_venda(
        fabrica.venda(
            totalAReceberFornecedor=D("10.00"),
            totalRecebidoFornec=D("5.00"),
            totalAPagarFornec=D("0"),
            totalPagoFornec=D("990.00"),
            pagamentos=[
                fabrica.pagamento(forma=2, valor=D("15.00"), dtVencto="2026-11-17 00:00:00"),
                fabrica.pagamento(forma=1),
            ],
        )
    )
    p = situacao_dos_pagamentos(v, HOJE)
    assert (p[0].situacao, p[0].vencido) == ("recebido_em_parte", False)
    assert (p[1].situacao, p[1].vencido) == ("sem_saldo", False)


def test_credito_vencido_quando_em_aberto() -> None:
    v = validar_venda(
        fabrica.venda(
            totalAReceberFornecedor=D("10.00"),
            totalRecebidoFornec=D("0"),
            pagamentos=[
                fabrica.pagamento(forma=2, valor=D("10.00"), dtVencto="2026-11-24 00:00:00")
            ],
        )
    )
    assert situacao_dos_pagamentos(v, HOJE)[0].vencido is True


def test_credito_lei_kandir_vem_como_esta() -> None:
    v = validar_venda(
        fabrica.venda(
            pagamentos=[
                fabrica.pagamento(forma=1, valor=D("1000.00")),
                fabrica.pagamento(forma=4, valor=D("-25.50")),
                fabrica.pagamento(forma=4, valor=D("10.00")),
            ]
        )
    )
    p = situacao_dos_pagamentos(v, HOJE)
    assert [x.valor_exibido for x in p] == [D("1000.00"), D("-25.50"), D("10.00")]
    assert [x.eh_credito for x in p] == [False, False, False]
    assert total_dos_pagamentos(v) == D("984.50")


def test_total_dos_pagamentos_sem_pagamentos_e_zero() -> None:
    assert total_dos_pagamentos(validar_venda(fabrica.venda(pagamentos=None))) == D("0")
