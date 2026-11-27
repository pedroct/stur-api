"""Quem desiste do pedido (Cancelar na tela, tempo limite, aba fechada) para o trabalho na API.

O servidor ASGI não cancela a rota quando o cliente sai: sem isto, a consulta abandonada espera
a vaga, busca todas as páginas na AGI e atrasa quem ficou.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

from fastapi import Request


class ClienteDesistiu(Exception):
    """O cliente desconectou antes da resposta. Ninguém a recebe: o status só vai ao log."""


async def ate_o_cliente_sair[T](pedido: Request, trabalho: Coroutine[Any, Any, T]) -> T:
    """Espera `trabalho` enquanto o cliente espera; se ele sair, cancela e levanta
    `ClienteDesistiu`. Só para pedido sem corpo: o que vier do cliente é lido e descartado."""
    tarefa = asyncio.create_task(trabalho)
    saida = asyncio.create_task(_esperar_desconexao(pedido))
    try:
        await asyncio.wait([tarefa, saida], return_when=asyncio.FIRST_COMPLETED)
        if tarefa.done():
            return tarefa.result()
        raise ClienteDesistiu
    finally:
        tarefa.cancel()
        saida.cancel()
        # a resposta só segue depois de o trabalho cortado terminar de se desfazer
        await asyncio.wait([tarefa, saida])


async def _esperar_desconexao(pedido: Request) -> None:
    while (await pedido.receive())["type"] != "http.disconnect":
        pass
