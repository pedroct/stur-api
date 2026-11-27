"""Estado do serviço de uma venda: a acontecer, em andamento ou concluído (PRD 8.3, IA 6.10).

Código puro: `hoje` entra de fora (a data da consulta em `America/Fortaleza`). As datas vêm do que
cada classificação tem: trechos (Aéreo e Rodoviário), entrada e saída (Hotelaria), retirada e
devolução (Locação), início e término (Diversos e Pacote). Venda cancelada ou sem as duas pontas
do período não tem estado.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import partial
from typing import Literal

from stur_api.agi.modelos import VendaAgi
from stur_api.dominio.datas import ler_data_hora
from stur_api.dominio.textos import normalizar

Estado = Literal["a_acontecer", "em_andamento", "concluido"]
Base = Literal["trechos", "entrada_saida", "retirada_devolucao", "inicio_termino"]


@dataclass(frozen=True)
class EstadoServico:
    estado: Estado
    inicio: date
    fim: date
    base: Base


def _periodo_dos_trechos(venda: VendaAgi) -> tuple[date | None, date | None]:
    inicios: list[date] = []
    fins: list[date] = []
    for trecho in venda.trechos or []:
        partida = ler_data_hora(trecho.dtPartida, "trechos[].dtPartida")
        chegada = ler_data_hora(trecho.dtChegada, "trechos[].dtChegada")
        primeira = partida or chegada
        ultima = chegada or partida
        if primeira is not None:
            inicios.append(primeira.date())
        if ultima is not None:
            fins.append(ultima.date())
    return (min(inicios) if inicios else None, max(fins) if fins else None)


def _periodo_dos_servicos(
    venda: VendaAgi, campo_inicio: str, campo_fim: str
) -> tuple[date | None, date | None]:
    inicios: list[date] = []
    fins: list[date] = []
    for servico in venda.detalheItem or []:
        inicio = ler_data_hora(getattr(servico, campo_inicio), f"detalheItem[].{campo_inicio}")
        fim = ler_data_hora(getattr(servico, campo_fim), f"detalheItem[].{campo_fim}")
        if inicio is not None:
            inicios.append(inicio.date())
        if fim is not None:
            fins.append(fim.date())
    return (min(inicios) if inicios else None, max(fins) if fins else None)


_FONTES: dict[str, tuple[Base, Callable[[VendaAgi], tuple[date | None, date | None]]]] = {
    "AEREO": ("trechos", _periodo_dos_trechos),
    "RODOVIARIO": ("trechos", _periodo_dos_trechos),
    "HOTELARIA": (
        "entrada_saida",
        partial(_periodo_dos_servicos, campo_inicio="dtEntrada", campo_fim="dtSaida"),
    ),
    "LOCACAO": (
        "retirada_devolucao",
        partial(_periodo_dos_servicos, campo_inicio="dtRetirada", campo_fim="dtDevolucao"),
    ),
    "DIVERSOS": (
        "inicio_termino",
        partial(_periodo_dos_servicos, campo_inicio="dtInicio", campo_fim="dtTermino"),
    ),
    "PACOTE": (
        "inicio_termino",
        partial(_periodo_dos_servicos, campo_inicio="dtInicio", campo_fim="dtTermino"),
    ),
}


def periodo_do_servico(venda: VendaAgi) -> tuple[date | None, date | None]:
    """Início e fim do serviço pelas datas da classificação; vale também na venda cancelada.

    Classificação sem regra dá `(None, None)`.
    """
    fonte = _FONTES.get(normalizar(venda.classificacaoproduto or ""))
    if fonte is None:
        return (None, None)
    return fonte[1](venda)


def estado_do_servico(venda: VendaAgi, hoje: date) -> EstadoServico | None:
    """Estado do serviço em `hoje`; `None` se cancelada, sem datas ou de classificação sem regra."""
    if normalizar(venda.status or "") == "CANCELADA":
        return None
    fonte = _FONTES.get(normalizar(venda.classificacaoproduto or ""))
    if fonte is None:
        return None
    inicio, fim = periodo_do_servico(venda)
    if inicio is None or fim is None:
        return None
    if hoje < inicio:
        estado: Estado = "a_acontecer"
    elif hoje <= fim:
        estado = "em_andamento"
    else:
        estado = "concluido"
    return EstadoServico(estado, inicio, fim, fonte[0])
