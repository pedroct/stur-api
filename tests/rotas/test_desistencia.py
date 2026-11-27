"""Quem desiste do pedido (Cancelar na tela, tempo limite, aba fechada) para o trabalho na API.

A aplicação é chamada direto pelo ASGI: o teste decide quando o cliente desconecta, o que o
`TestClient` não permite.
"""

import asyncio
from typing import Any

import pytest

from stur_api.agi.cliente import FiltroAgi
from stur_api.main import criar_app
from stur_api.servicos.consultas import ServicoConsulta

PRAZO_S = 1


class AgiPresa:
    """Busca falsa que só responde quando `soltar` for ligado; conta o que começou e foi cortado."""

    def __init__(self) -> None:
        self.soltar = asyncio.Event()
        self.comecadas: list[FiltroAgi] = []
        self.cortadas = 0

    async def buscar_vendas(self, filtro: FiltroAgi) -> list[dict[str, Any]]:
        if filtro.so_primeira_pagina:
            return []
        self.comecadas.append(filtro)
        try:
            await self.soltar.wait()
        except asyncio.CancelledError:
            self.cortadas += 1
            raise
        return []

    async def esperar_comecadas(self, quantas: int) -> None:
        async with asyncio.timeout(PRAZO_S):
            while len(self.comecadas) < quantas:
                await asyncio.sleep(0)


class Pedido:
    """Um GET pelo ASGI, com um cliente que desconecta quando o teste chama `desistir`."""

    def __init__(self, app: Any, caminho: str, query: str = "") -> None:
        self._saiu = asyncio.Event()
        self._corpo_entregue = False
        self.status: int | None = None
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": caminho,
            "raw_path": caminho.encode(),
            "query_string": query.encode(),
            "root_path": "",
            "headers": [(b"host", b"teste")],
            "client": ("127.0.0.1", 1),
            "server": ("teste", 80),
        }
        self.tarefa = asyncio.create_task(app(scope, self._receber, self._enviar))

    async def _receber(self) -> dict[str, Any]:
        if not self._corpo_entregue:
            self._corpo_entregue = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self._saiu.wait()
        return {"type": "http.disconnect"}

    async def _enviar(self, mensagem: dict[str, Any]) -> None:
        if mensagem["type"] == "http.response.start":
            self.status = mensagem["status"]

    def desistir(self) -> None:
        self._saiu.set()

    async def terminar(self) -> None:
        await asyncio.wait_for(asyncio.shield(self.tarefa), PRAZO_S)


def _lista(dia: int) -> tuple[str, str]:
    return "/api/v1/vendas", f"de=2026-11-{dia:02d}&ate=2026-11-{dia:02d}"


@pytest.fixture
def presa(servico: ServicoConsulta, monkeypatch: pytest.MonkeyPatch) -> AgiPresa:
    agi_presa = AgiPresa()
    monkeypatch.setattr(servico._cliente, "buscar_vendas", agi_presa.buscar_vendas)
    return agi_presa


@pytest.mark.parametrize(
    "caminho_query",
    [
        _lista(1),
        ("/api/v1/reservas/90000001", ""),
        ("/api/v1/reservas/90000001/vendas/1001", ""),
        ("/api/v1/reservas/90000001/vendas/1001/dado-cru", ""),
    ],
    ids=["lista", "reserva", "venda", "dado-cru"],
)
async def test_quem_desiste_corta_a_busca_em_andamento(
    servico: ServicoConsulta, presa: AgiPresa, caminho_query: tuple[str, str]
) -> None:
    pedido = Pedido(criar_app(servico), *caminho_query)
    await presa.esperar_comecadas(1)

    pedido.desistir()
    await pedido.terminar()

    assert presa.cortadas == 1
    assert pedido.status == 499


async def test_quem_desiste_na_fila_nao_chega_a_chamar_a_agi(
    servico: ServicoConsulta, presa: AgiPresa
) -> None:
    app = criar_app(servico)
    ocupando = [Pedido(app, *_lista(dia)) for dia in (1, 2)]
    await presa.esperar_comecadas(2)
    na_fila = Pedido(app, *_lista(3))
    await asyncio.sleep(0.02)

    na_fila.desistir()
    await na_fila.terminar()
    presa.soltar.set()
    for pedido in ocupando:
        await pedido.terminar()

    assert len(presa.comecadas) == 2
    assert [p.status for p in ocupando] == [200, 200]


async def test_a_vaga_de_quem_desistiu_passa_para_o_proximo(
    servico: ServicoConsulta, presa: AgiPresa
) -> None:
    app = criar_app(servico)
    ocupando = [Pedido(app, *_lista(dia)) for dia in (1, 2)]
    await presa.esperar_comecadas(2)
    seguinte = Pedido(app, *_lista(3))

    ocupando[0].desistir()
    await presa.esperar_comecadas(3)
    presa.soltar.set()
    for pedido in (*ocupando, seguinte):
        await pedido.terminar()

    assert seguinte.status == 200
    assert presa.cortadas == 1


async def test_quem_fica_recebe_a_resposta(servico: ServicoConsulta, presa: AgiPresa) -> None:
    presa.soltar.set()
    pedido = Pedido(criar_app(servico), *_lista(1))

    await pedido.terminar()

    assert pedido.status == 200
    assert presa.cortadas == 0
