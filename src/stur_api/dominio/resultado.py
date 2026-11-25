"""Filtros locais, ordem e resumo do resultado da lista (PRD 8.2 e 8.5b)."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from stur_api.dominio.consulta import ConsultaVendas
from stur_api.dominio.contas import ZERO, percentual_lucro
from stur_api.dominio.datas import ler_data_hora
from stur_api.dominio.textos import contem, normalizar
from stur_api.dominio.vendas import CANCELADA, ResumoVenda


@dataclass(frozen=True)
class ResumoIncentivos:
    quantidade: int
    valor: Decimal  # Σ margem dos incentivos ativos
    margem_com_incentivos: Decimal
    percentual_com_incentivos: Decimal | None


@dataclass(frozen=True)
class ResumoResultado:
    quantidade: int  # vendas a cliente, sem canceladas e sem incentivos
    total_cliente: Decimal
    total_fornecedor: Decimal
    margem: Decimal
    percentual_lucro: Decimal | None
    nao_fecham: int  # todas as linhas cuja conta não fecha
    canceladas: int
    incentivos: ResumoIncentivos


def _casa(texto: str | None, busca: str | None) -> bool:
    """Busca vazia ou ausente não filtra nada (nem esconde venda com o campo ausente)."""
    if not busca:
        return True
    return contem(texto, busca)


def aplicar_filtros(resumos: list[ResumoVenda], c: ConsultaVendas) -> list[ResumoVenda]:
    classificacoes = {normalizar(x) for x in c.classificacoes}
    achados: list[ResumoVenda] = []
    for r in resumos:
        if c.situacoes and r.situacao not in c.situacoes:
            continue
        if classificacoes and normalizar(r.classificacao or "") not in classificacoes:
            continue
        if c.fornecedor and not (
            _casa(r.fornecedor, c.fornecedor) or _casa(r.fornecedor2, c.fornecedor)
        ):
            continue
        # `contem` de campo ausente é falso: sem texto de busca o filtro nem é consultado
        if not (_casa(r.cliente, c.cliente) and _casa(r.emissor, c.emissor)):
            continue
        achados.append(r)
    return achados


def _data_do_tipo(r: ResumoVenda, c: ConsultaVendas) -> datetime | None:
    if c.tipo_data == "confirmacao":
        return ler_data_hora(r.data_confirmacao, "dtconfirmacao")
    if c.tipo_data == "alteracao":
        return ler_data_hora(r.data_alteracao, "dtalteracao")
    return ler_data_hora(r.data_emissao, "dtemissao")


def ordenar_resultado(resumos: list[ResumoVenda], c: ConsultaVendas) -> list[ResumoVenda]:
    """Com período: data do tipo consultado, mais recente primeiro, empate por `idreserva`
    decrescente, sem data por último. Só com número: ordem de lançamento (`idreserva` crescente)."""
    if c.de is None or c.ate is None:
        return sorted(resumos, key=lambda r: r.idreserva or 0)

    com_data: list[tuple[datetime, int, ResumoVenda]] = []
    sem_data: list[ResumoVenda] = []
    for r in resumos:
        data = _data_do_tipo(r, c)
        if data is None:
            sem_data.append(r)
        else:
            com_data.append((data, r.idreserva or 0, r))
    com_data.sort(key=lambda t: (t[0], t[1]), reverse=True)
    sem_data.sort(key=lambda r: r.idreserva or 0, reverse=True)
    return [r for _, _, r in com_data] + sem_data


def resumir_resultado(resumos: list[ResumoVenda]) -> ResumoResultado:
    """Quantidade, totais e margem das vendas a cliente (fee incluído); incentivos à parte."""
    clientes = [r for r in resumos if r.tipo != "incentivo" and r.situacao != CANCELADA]
    incentivos = [r for r in resumos if r.tipo == "incentivo" and r.situacao != CANCELADA]
    total_cliente = sum((r.total_cliente for r in clientes), start=ZERO)
    margem = sum((r.margem for r in clientes), start=ZERO)
    valor_incentivos = sum((r.margem for r in incentivos), start=ZERO)
    margem_com_incentivos = margem + valor_incentivos
    return ResumoResultado(
        quantidade=len(clientes),
        total_cliente=total_cliente,
        total_fornecedor=sum((r.total_fornecedor for r in clientes), start=ZERO),
        margem=margem,
        percentual_lucro=percentual_lucro(margem, total_cliente),
        nao_fecham=sum(1 for r in resumos if not r.conta_fecha),
        canceladas=sum(1 for r in resumos if r.situacao == CANCELADA),
        incentivos=ResumoIncentivos(
            quantidade=len(incentivos),
            valor=valor_incentivos,
            margem_com_incentivos=margem_com_incentivos,
            percentual_com_incentivos=percentual_lucro(margem_com_incentivos, total_cliente),
        ),
    )


def vendas_no_resultado(resumos: list[ResumoVenda]) -> dict[int, int]:
    """Quantas linhas o resultado tem por número de reserva."""
    return dict(Counter(r.numero for r in resumos if r.numero is not None))
