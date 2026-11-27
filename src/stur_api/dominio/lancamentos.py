"""Situação dos recebimentos e pagamentos, derivada dos totais da venda (PRD 8.3).

A AGI não diz se cada lançamento foi quitado: só traz totais a receber/pagar e já recebidos/pagos
da venda inteira. A situação sai desses totais e vale para todos os lançamentos da mesma lista.
Código puro: `hoje` entra de fora (a data da consulta em `America/Fortaleza`). Total ausente
(`None`) conta como zero.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from stur_api.agi.modelos import VendaAgi
from stur_api.dominio.datas import ler_data_hora

ZERO = Decimal("0")
FORMA_CREDITO = 2  # Crédito do fornecedor: aparece negativo e abate o total (PRD 8.3 e 8.5b)

SituacaoLancamento = Literal["previsto", "sem_saldo", "em_aberto", "recebido_em_parte"]


TipoDocumento = Literal["recibo", "nota_debito", "nota_credito", "outro"]


@dataclass(frozen=True)
class Documento:
    tipo: TipoDocumento
    numero: str


@dataclass(frozen=True)
class LancamentoCalculado:
    indice: int  # posição na lista da AGI
    valor_exibido: Decimal
    eh_credito: bool
    situacao: SituacaoLancamento
    vencido: bool
    cartao_repassado: bool
    descricao_forma: str | None  # o texto da forma (`descricaoForma`), não o código `forma`
    vencimento: str | None  # `dtVencto` como veio
    documentos: list[Documento]


def _situacao(a_receber: Decimal | None, recebido: Decimal | None) -> SituacaoLancamento:
    if (a_receber or ZERO) == ZERO:
        return "sem_saldo"
    if (recebido or ZERO) == ZERO:
        return "em_aberto"
    return "recebido_em_parte"


def _vencido(situacao: SituacaoLancamento, vencimento: str | None, hoje: date, campo: str) -> bool:
    if situacao != "em_aberto":
        return False
    data = ler_data_hora(vencimento, campo)
    return data is not None and data.date() < hoje


def _documentos(*pares: tuple[TipoDocumento, str | None]) -> list[Documento]:
    """Os documentos preenchidos, na ordem dada, cada número uma vez só.

    A AGI repete em `documentosFinanceiro` o número que já veio em `numRecibo` ou `numNotaDebito`,
    e junta vários números nesse campo, separados por vírgula. Os do tipo `outro` saem um a um, e um
    número já incluído não entra de novo (vale o primeiro tipo).
    """
    documentos: list[Documento] = []
    vistos: set[str] = set()
    for tipo, valor in pares:
        if not valor:
            continue
        numeros = [n.strip() for n in valor.split(",")] if tipo == "outro" else [valor]
        for numero in numeros:
            chave = numero.strip()
            if numero and chave not in vistos:
                vistos.add(chave)
                documentos.append(Documento(tipo, numero))
    return documentos


def situacao_dos_recebimentos(venda: VendaAgi, hoje: date) -> list[LancamentoCalculado]:
    reservada = venda.status == "RESERVADA"
    da_venda = _situacao(venda.totalAReceberCliente, venda.totalRecebidoCliente)
    calculados: list[LancamentoCalculado] = []
    for indice, recebimento in enumerate(venda.recebimentos or []):
        situacao: SituacaoLancamento = "previsto" if reservada else da_venda
        calculados.append(
            LancamentoCalculado(
                indice=indice,
                valor_exibido=recebimento.valor or ZERO,
                eh_credito=False,
                situacao=situacao,
                vencido=_vencido(situacao, recebimento.dtVencto, hoje, "recebimentos[].dtVencto"),
                cartao_repassado=bool(recebimento.cartaoRepassadoAoFornecedor),
                descricao_forma=recebimento.descricaoForma,
                vencimento=recebimento.dtVencto,
                documentos=_documentos(
                    ("recibo", recebimento.numRecibo),
                    ("nota_debito", recebimento.numNotaDebito),
                    ("nota_credito", recebimento.numNotaCredito),
                    ("outro", recebimento.documentosFinanceiro),
                ),
            )
        )
    return calculados


def situacao_dos_pagamentos(venda: VendaAgi, hoje: date) -> list[LancamentoCalculado]:
    reservada = venda.status == "RESERVADA"
    a_pagar = _situacao(venda.totalAPagarFornec, venda.totalPagoFornec)
    do_credito = _situacao(venda.totalAReceberFornecedor, venda.totalRecebidoFornec)
    calculados: list[LancamentoCalculado] = []
    for indice, pagamento in enumerate(venda.pagamentos or []):
        valor = pagamento.valor or ZERO
        eh_credito = pagamento.forma == FORMA_CREDITO
        situacao: SituacaoLancamento = do_credito if eh_credito else a_pagar
        if reservada:
            situacao = "previsto"
        calculados.append(
            LancamentoCalculado(
                indice=indice,
                valor_exibido=-valor if eh_credito else valor,
                eh_credito=eh_credito,
                situacao=situacao,
                vencido=_vencido(situacao, pagamento.dtVencto, hoje, "pagamentos[].dtVencto"),
                cartao_repassado=False,
                descricao_forma=pagamento.descricaoForma,
                vencimento=pagamento.dtVencto,
                documentos=_documentos(("outro", pagamento.documentosFinanceiro)),
            )
        )
    return calculados


def total_dos_pagamentos(venda: VendaAgi) -> Decimal:
    """Soma das outras formas menos a soma dos créditos (forma 2)."""
    total = ZERO
    for pagamento in venda.pagamentos or []:
        valor = pagamento.valor or ZERO
        total += -valor if pagamento.forma == FORMA_CREDITO else valor
    return total
