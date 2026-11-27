"""Quantas consultas de período buscam na AGI ao mesmo tempo (`CONSULTAS_SIMULTANEAS`)."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import pytest

from stur_api.agi.cliente import ClienteAgi, FiltroAgi
from stur_api.config import Configuracao
from stur_api.dominio.consulta import ConsultaVendas
from stur_api.erros import ApiSturSemResposta
from stur_api.servicos.consultas import ServicoConsulta
from tests.conftest import RelogioFixo

Busca = Callable[[FiltroAgi], Awaitable[list[dict[str, Any]]]]


def _consulta(dia: int) -> ConsultaVendas:
    return ConsultaVendas(None, de=date(2026, 11, dia), ate=date(2026, 11, dia))


class AgiContada:
    """Busca falsa que conta as buscas do período; a da data da cópia fica fora da conta."""

    def __init__(self, espera_s: float = 0.0) -> None:
        self._espera_s = espera_s
        self.chamadas = 0
        self.ativas = 0
        self.maximo_ativas = 0

    async def buscar_vendas(self, filtro: FiltroAgi) -> list[dict[str, Any]]:
        if filtro.so_primeira_pagina:
            return []
        self.chamadas += 1
        self.ativas += 1
        self.maximo_ativas = max(self.maximo_ativas, self.ativas)
        try:
            await asyncio.sleep(self._espera_s)
        finally:
            self.ativas -= 1
        return []


class AgiPresa:
    """Busca falsa que só responde quando `soltar` for ligado."""

    def __init__(self) -> None:
        self.soltar = asyncio.Event()
        self.presas = 0

    async def buscar_vendas(self, filtro: FiltroAgi) -> list[dict[str, Any]]:
        if filtro.so_primeira_pagina:
            return []
        self.presas += 1
        await self.soltar.wait()
        return []

    async def esperar_presas(self, quantas: int) -> None:
        async with asyncio.timeout(1):
            while self.presas < quantas:
                await asyncio.sleep(0)


def _trocar_busca(monkeypatch: pytest.MonkeyPatch, servico: ServicoConsulta, busca: Busca) -> None:
    monkeypatch.setattr(servico._cliente, "buscar_vendas", busca)


async def test_no_maximo_duas_buscas_ao_mesmo_tempo(
    servico: ServicoConsulta, monkeypatch: pytest.MonkeyPatch
) -> None:
    agi = AgiContada(espera_s=0.02)
    _trocar_busca(monkeypatch, servico, agi.buscar_vendas)
    resultados = await asyncio.gather(
        *(servico.consultar_vendas(_consulta(dia), atualizar=False) for dia in range(1, 6))
    )
    assert agi.maximo_ativas == 2
    assert [r.consulta.de for r in resultados] == [date(2026, 11, dia) for dia in range(1, 6)]


async def test_falhas_liberam_a_vaga(
    servico: ServicoConsulta, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _sem_resposta(_filtro: FiltroAgi) -> list[dict[str, Any]]:
        raise ApiSturSemResposta(30)

    _trocar_busca(monkeypatch, servico, _sem_resposta)
    for dia in range(1, 4):
        with pytest.raises(ApiSturSemResposta):
            await asyncio.wait_for(servico.consultar_vendas(_consulta(dia), atualizar=False), 1)
    _trocar_busca(monkeypatch, servico, AgiContada().buscar_vendas)
    resultado = await asyncio.wait_for(servico.consultar_vendas(_consulta(4), atualizar=False), 1)
    assert resultado.consulta.de == date(2026, 11, 4)


async def test_cancelamento_libera_a_vaga(
    servico: ServicoConsulta, monkeypatch: pytest.MonkeyPatch
) -> None:
    presa = AgiPresa()
    _trocar_busca(monkeypatch, servico, presa.buscar_vendas)
    tarefas = [
        asyncio.create_task(servico.consultar_vendas(_consulta(dia), atualizar=False))
        for dia in (1, 2)
    ]
    await presa.esperar_presas(2)
    for tarefa in tarefas:
        tarefa.cancel()
    desfechos = await asyncio.gather(*tarefas, return_exceptions=True)
    assert all(isinstance(d, asyncio.CancelledError) for d in desfechos)
    _trocar_busca(monkeypatch, servico, AgiContada().buscar_vendas)
    resultado = await asyncio.wait_for(servico.consultar_vendas(_consulta(3), atualizar=False), 1)
    assert resultado.consulta.de == date(2026, 11, 3)


async def test_quem_esperou_aproveita_o_resultado_igual(
    config: Configuracao,
    cliente: ClienteAgi,
    relogio: RelogioFixo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config.consultas_simultaneas = 1
    servico = ServicoConsulta(config, cliente, relogio)
    agi = AgiContada(espera_s=0.02)
    _trocar_busca(monkeypatch, servico, agi.buscar_vendas)
    primeiro, segundo = await asyncio.gather(
        servico.consultar_vendas(_consulta(1), atualizar=False),
        servico.consultar_vendas(_consulta(1), atualizar=False),
    )
    assert agi.chamadas == 1
    assert primeiro is segundo


async def test_resultado_guardado_nao_espera_vaga(
    servico: ServicoConsulta, monkeypatch: pytest.MonkeyPatch
) -> None:
    _trocar_busca(monkeypatch, servico, AgiContada().buscar_vendas)
    guardado = await servico.consultar_vendas(_consulta(1), atualizar=False)

    presa = AgiPresa()
    _trocar_busca(monkeypatch, servico, presa.buscar_vendas)
    ocupando = [
        asyncio.create_task(servico.consultar_vendas(_consulta(dia), atualizar=False))
        for dia in (2, 3)
    ]
    await presa.esperar_presas(2)
    try:
        achado = await asyncio.wait_for(
            servico.consultar_vendas(_consulta(1), atualizar=False), 0.1
        )
        assert achado is guardado
    finally:
        presa.soltar.set()
        await asyncio.gather(*ocupando)
