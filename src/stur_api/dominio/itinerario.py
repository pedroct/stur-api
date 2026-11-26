"""Itinerário dos trechos aéreos: trajetos, esperas e estadias (PRD 8.3, IA 6.10).

Código puro. Todo índice é a posição do trecho na lista da API; a ordem dos trechos é a do
`segmento` (estável: segmentos iguais ou ausentes mantêm a ordem da API). Os horários são locais
de cada aeroporto, sem fuso. Espera só existe com os dois horários: hora 00:00:00 ou data vazia
conta como "sem horário", e a forma do itinerário diz isso (`sem_dados`, `so_datas`).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from stur_api.agi.modelos import LocalTrechoAgi, TrechoAgi
from stur_api.dominio.datas import ler_data_hora, tem_horario

Forma = Literal["sem_dados", "so_datas", "com_horario"]


@dataclass(frozen=True)
class Espera:
    apos_trecho: int  # índice do trecho depois do qual se espera
    minutos: int
    aeroporto: str


@dataclass(frozen=True)
class Trajeto:
    trechos: list[int]
    esperas: list[Espera]


@dataclass(frozen=True)
class Estadia:
    apos_trajeto: int  # posição do trajeto na lista de trajetos
    dias: int
    sigla: str
    cidade: str | None


@dataclass(frozen=True)
class Itinerario:
    forma: Forma
    trajetos: list[Trajeto]
    estadias: list[Estadia]


def sigla_do_local(local: LocalTrechoAgi | None) -> str | None:
    return (local.sigla if local else None) or None


def _continua_trajeto(
    anterior: TrechoAgi,
    atual: TrechoAgi,
    chegada: datetime | None,
    partida: datetime | None,
    corte: timedelta,
) -> bool:
    saida = sigla_do_local(atual.origem)
    if saida is None or saida != sigla_do_local(anterior.destino):
        return False
    if chegada is None or partida is None:
        return False
    return partida - chegada < corte


def _espera(
    anterior: int,
    atual: int,
    trechos: list[TrechoAgi],
    chegadas: list[datetime | None],
    partidas: list[datetime | None],
) -> Espera | None:
    chegada, partida = chegadas[anterior], partidas[atual]
    if chegada is None or partida is None or not (tem_horario(chegada) and tem_horario(partida)):
        return None
    localizador = (trechos[anterior].localizador or "").strip()
    if not localizador or localizador != (trechos[atual].localizador or "").strip():
        return None
    minutos = int((partida - chegada).total_seconds() // 60)
    if minutos <= 0:
        return None
    return Espera(anterior, minutos, sigla_do_local(trechos[anterior].destino) or "")


def _forma(
    trechos: list[TrechoAgi], chegadas: list[datetime | None], partidas: list[datetime | None]
) -> Forma:
    datas = [*partidas, *chegadas]
    if all(d is None for d in datas):
        return "sem_dados"
    if any((t.voo or "").strip() for t in trechos) or any(tem_horario(d) for d in datas):
        return "com_horario"
    return "so_datas"


def _agrupar(
    trechos: list[TrechoAgi],
    chegadas: list[datetime | None],
    partidas: list[datetime | None],
    corte: timedelta,
) -> list[list[int]]:
    """Índices dos trechos em ordem de segmento, agrupados por trajeto contínuo."""
    ordem = sorted(
        range(len(trechos)), key=lambda i: (trechos[i].segmento is None, trechos[i].segmento or 0)
    )
    grupos: list[list[int]] = []
    for i in ordem:
        if grupos and _continua_trajeto(
            trechos[grupos[-1][-1]], trechos[i], chegadas[grupos[-1][-1]], partidas[i], corte
        ):
            grupos[-1].append(i)
        else:
            grupos.append([i])
    return grupos


def _estadias(
    grupos: list[list[int]],
    trechos: list[TrechoAgi],
    chegadas: list[datetime | None],
    partidas: list[datetime | None],
) -> list[Estadia]:
    """Dias entre a chegada de um trajeto e a partida do seguinte."""
    estadias = []
    for posicao, (antes, depois) in enumerate(zip(grupos, grupos[1:], strict=False)):
        ultima, primeira = antes[-1], depois[0]
        chegada, partida = chegadas[ultima], partidas[primeira]
        if chegada is None or partida is None:
            continue
        dias = (partida.date() - chegada.date()).days
        if dias < 0:
            continue
        destino = trechos[ultima].destino
        estadias.append(
            Estadia(
                posicao,
                dias,
                sigla_do_local(destino) or "",
                (destino.cidade if destino else None) or None,
            )
        )
    return estadias


def montar_itinerario(trechos: list[TrechoAgi], corte_horas: int) -> Itinerario | None:
    """Trajetos, esperas e estadias dos trechos; `None` quando não há trechos."""
    if not trechos:
        return None
    partidas = [ler_data_hora(t.dtPartida, "trechos[].dtPartida") for t in trechos]
    chegadas = [ler_data_hora(t.dtChegada, "trechos[].dtChegada") for t in trechos]
    grupos = _agrupar(trechos, chegadas, partidas, timedelta(hours=corte_horas))
    trajetos = [
        Trajeto(
            grupo,
            [
                e
                for anterior, atual in zip(grupo, grupo[1:], strict=False)
                if (e := _espera(anterior, atual, trechos, chegadas, partidas)) is not None
            ],
        )
        for grupo in grupos
    ]
    estadias = _estadias(grupos, trechos, chegadas, partidas)
    return Itinerario(_forma(trechos, chegadas, partidas), trajetos, estadias)
