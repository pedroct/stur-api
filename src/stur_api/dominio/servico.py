"""Resumo do serviço de uma venda para a lista da reserva (PRD 8.1, IA 6.10).

Código puro. O período vem de `periodo_do_servico`; a rota encadeia os trechos só pelas siglas
(sem olhar datas, ao contrário do itinerário, que separa trajetos por tempo).
"""

from dataclasses import dataclass
from datetime import date

from stur_api.agi.modelos import ServicoAgi, TrechoAgi, VendaAgi
from stur_api.dominio.estado_servico import periodo_do_servico
from stur_api.dominio.itinerario import sigla_do_local
from stur_api.dominio.textos import normalizar


@dataclass(frozen=True)
class ResumoServico:
    quantidade: int  # serviços em `detalheItem`
    inicio: date | None
    fim: date | None
    rota: list[list[str]]  # siglas dos aeroportos, um item por trajeto
    diarias: int | None  # hotelaria e locação
    descricao: str | None  # Diversos e Pacote


def _rota(trechos: list[TrechoAgi]) -> list[list[str]]:
    """Trechos na ordem do `segmento`; um item novo quando a origem não é o destino anterior."""
    ordenados = sorted(trechos, key=lambda t: (t.segmento is None, t.segmento or 0))
    rota: list[list[str]] = []
    for trecho in ordenados:
        origem, destino = sigla_do_local(trecho.origem), sigla_do_local(trecho.destino)
        if origem is None or destino is None:
            continue
        if rota and rota[-1][-1] == origem:
            rota[-1].append(destino)
        else:
            rota.append([origem, destino])
    return rota


def _primeiro(venda: VendaAgi) -> ServicoAgi | None:
    return venda.detalheItem[0] if venda.detalheItem else None


def _diarias(venda: VendaAgi, classificacao: str) -> int | None:
    primeiro = _primeiro(venda)
    if primeiro is None:
        return None
    if classificacao == "HOTELARIA":
        diarias = [a.qtdeDiarias for a in primeiro.apartamentos or [] if a.qtdeDiarias is not None]
        return max(diarias) if diarias else None
    if classificacao == "LOCACAO":
        return primeiro.qtdeDiarias
    return None


def _descricao(venda: VendaAgi, classificacao: str) -> str | None:
    primeiro = _primeiro(venda)
    if primeiro is None or classificacao not in {"DIVERSOS", "PACOTE"}:
        return None
    return primeiro.descricao


def resumo_do_servico(venda: VendaAgi) -> ResumoServico | None:
    """Resumo do serviço; `None` só sem `detalheItem` e sem `trechos`."""
    if not venda.detalheItem and not venda.trechos:
        return None
    classificacao = normalizar(venda.classificacaoproduto or "")
    inicio, fim = periodo_do_servico(venda)
    return ResumoServico(
        quantidade=len(venda.detalheItem or []),
        inicio=inicio,
        fim=fim,
        rota=_rota(venda.trechos or []),
        diarias=_diarias(venda, classificacao),
        descricao=_descricao(venda, classificacao),
    )
