"""Tipo da venda, resumo para a lista e totais da reserva (PRD 8.1, 8.4 e 8.5b).

Código puro, sem entrada nem saída. Campo ausente na AGI conta como zero nos valores e como
`None` nos textos. As datas seguem como a AGI as devolve (texto local sem fuso).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from stur_api.agi.modelos import VendaAgi
from stur_api.config import Configuracao
from stur_api.dominio.contas import ZERO, conta_do_servico, percentual_lucro, verificar_totais
from stur_api.dominio.textos import normalizar

TipoVenda = Literal["venda", "fee", "incentivo"]

_CANCELADA = "cancelada"


@dataclass(frozen=True)
class ResumoVenda:
    numero: int | None
    idreserva: int | None
    produto: str | None
    classificacao: str | None
    categoria: str | None
    cliente: str | None
    fornecedor: str | None
    fornecedor2: str | None
    emissor: str | None
    data_emissao: str | None
    data_confirmacao: str | None
    data_alteracao: str | None
    situacao: str | None  # `status` da AGI em minúsculas: "fechada", "cancelada"...
    total_cliente: Decimal
    total_fornecedor: Decimal
    margem: Decimal
    percentual_lucro: Decimal | None
    conta_fecha: bool
    tipo: TipoVenda
    id_venda_fee: int | None  # venda comum ligada a uma venda de fee (`idreservavinculadafee`)
    passageiros: list[str]


@dataclass(frozen=True)
class TotaisReserva:
    quantidade: int  # todas as vendas, canceladas incluídas
    quantidade_canceladas: int
    total_cliente: Decimal  # só as não canceladas
    total_fornecedor: Decimal
    margem: Decimal
    percentual_lucro: Decimal | None


def _vinculo_de_fee(venda: VendaAgi) -> int:
    return venda.idreservavinculadafee or 0


def tipo_da_venda(venda: VendaAgi, config: Configuracao) -> TipoVenda:
    """Incentivo pelo produto; fee só com produto de fee e vínculo (PRD 8.4); o resto é venda."""
    produto = normalizar(venda.nomeproduto or "")
    if produto in {normalizar(p) for p in config.produtos_incentivo}:
        return "incentivo"
    if produto in {normalizar(p) for p in config.produtos_fee} and _vinculo_de_fee(venda) != 0:
        return "fee"
    return "venda"


def _passageiros(venda: VendaAgi) -> list[str]:
    nomes: list[str] = []
    for servico in venda.detalheItem or []:
        nome = servico.nomePaxCompleto or servico.nomePax
        if nome and nome not in nomes:
            nomes.append(nome)
    return nomes


def resumir(venda: VendaAgi, config: Configuracao) -> ResumoVenda:
    """Linha da lista: valores da API, tipo, passageiros e se a conta dos serviços fecha."""
    status = venda.status or ""
    contas = [
        conta_do_servico(servico, indice, status)
        for indice, servico in enumerate(venda.detalheItem or [], start=1)
    ]
    total_cliente = ZERO if venda.totalCliente is None else venda.totalCliente
    margem = ZERO if venda.margemLucroBruta is None else venda.margemLucroBruta
    tipo = tipo_da_venda(venda, config)
    vinculo = _vinculo_de_fee(venda)
    return ResumoVenda(
        numero=venda.reserva,
        idreserva=venda.idreserva,
        produto=venda.nomeproduto,
        classificacao=venda.classificacaoproduto,
        categoria=venda.categoriaproduto,
        cliente=venda.nomecliente,
        fornecedor=venda.nomefornec,
        fornecedor2=venda.nomefornec2,
        emissor=venda.nomeEmissor,
        data_emissao=venda.dtemissao,
        data_confirmacao=venda.dtconfirmacao,
        data_alteracao=venda.dtalteracao,
        situacao=None if venda.status is None else venda.status.lower(),
        total_cliente=total_cliente,
        total_fornecedor=ZERO if venda.totalFornecedor is None else venda.totalFornecedor,
        margem=margem,
        percentual_lucro=percentual_lucro(margem, total_cliente),
        conta_fecha=verificar_totais(venda, contas, config).fecha,
        tipo=tipo,
        id_venda_fee=vinculo if tipo == "venda" and vinculo != 0 else None,
        passageiros=_passageiros(venda),
    )


def ordenar_por_lancamento(vendas: list[VendaAgi]) -> list[VendaAgi]:
    """Ordem em que as vendas foram lançadas: `idreserva` crescente (hierarquia, PRD 8.1)."""
    return sorted(vendas, key=lambda v: v.idreserva or 0)


def totais_da_reserva(resumos: list[ResumoVenda]) -> TotaisReserva:
    """Soma só as vendas não canceladas; a quantidade conta todas (PRD 8.1)."""
    ativas = [r for r in resumos if r.situacao != _CANCELADA]
    total_cliente = sum((r.total_cliente for r in ativas), start=ZERO)
    margem = sum((r.margem for r in ativas), start=ZERO)
    return TotaisReserva(
        quantidade=len(resumos),
        quantidade_canceladas=len(resumos) - len(ativas),
        total_cliente=total_cliente,
        total_fornecedor=sum((r.total_fornecedor for r in ativas), start=ZERO),
        margem=margem,
        percentual_lucro=percentual_lucro(margem, total_cliente),
    )
