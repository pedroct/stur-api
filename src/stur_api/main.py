"""Aplicação: rotas, ciclo de vida e tradução dos erros para o envelope do contrato.

Erros ao cliente sempre `{"codigo", "mensagem", "detalhe"}` (mais `campo` nos 422), sem eco do
valor recebido e sem traceback.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from stur_api.agi.cliente import ClienteAgi
from stur_api.config import Configuracao
from stur_api.erros import ConsultaInvalida, ErroAplicacao, ErroInterno
from stur_api.relogio import RelogioSistema
from stur_api.rotas import parametros, reservas, saude, vendas
from stur_api.servicos.consultas import ServicoConsulta

PARAMETRO_INVALIDO = "parametro_invalido"
MENSAGEM_PARAMETRO_INVALIDO = "Um parâmetro da consulta está num formato inválido."


def criar_app(servico: ServicoConsulta | None = None) -> FastAPI:
    """Sem `servico`, o ciclo de vida monta o real a partir do ambiente (`Configuracao`)."""

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        if servico is not None:
            yield
            return
        config = Configuracao()
        relogio = RelogioSistema()
        async with httpx.AsyncClient(timeout=config.agi_tempo_limite_s) as http:
            app.state.servico = ServicoConsulta(config, ClienteAgi(config, http, relogio), relogio)
            yield

    app = FastAPI(title="stur-api", version="0.1.0", lifespan=ciclo_de_vida)
    if servico is not None:
        app.state.servico = servico
    app.exception_handler(ErroAplicacao)(_erro_da_aplicacao)
    app.exception_handler(RequestValidationError)(_parametro_invalido)
    app.exception_handler(Exception)(_erro_inesperado)
    for modulo in (saude, parametros, vendas, reservas):
        app.include_router(modulo.roteador, prefix="/api/v1")
    return app


def _resposta(status: int, codigo: str, mensagem: str, detalhe: Any, **extra: Any) -> JSONResponse:
    corpo = {"codigo": codigo, "mensagem": mensagem, "detalhe": detalhe, **extra}
    return JSONResponse(jsonable_encoder(corpo), status_code=status)


def _erro_da_aplicacao(_pedido: Request, erro: ErroAplicacao) -> JSONResponse:
    extra = {"campo": erro.campo} if isinstance(erro, ConsultaInvalida) else {}
    return _resposta(erro.status_http, erro.codigo, erro.mensagem, erro.detalhe, **extra)


def _parametro_invalido(_pedido: Request, erro: RequestValidationError) -> JSONResponse:
    """422 com o nome do parâmetro e o tipo do erro; nunca o valor recebido (`input`)."""
    problemas = [(_nome_do_parametro(e["loc"]), str(e["type"])) for e in erro.errors()]
    return _resposta(
        422,
        PARAMETRO_INVALIDO,
        MENSAGEM_PARAMETRO_INVALIDO,
        [f"{nome}: {tipo}" for nome, tipo in problemas],
        campo=problemas[0][0] if problemas else None,
    )


def _nome_do_parametro(loc: tuple[int | str, ...]) -> str:
    """`("query", "situacao", 1)` → `"situacao"`: o nome como a query o escreve."""
    nomes = [str(parte) for parte in loc[1:] if isinstance(parte, str)]
    return nomes[0] if nomes else str(loc[0])


def _erro_inesperado(_pedido: Request, _erro: Exception) -> JSONResponse:
    erro = ErroInterno()
    return _resposta(erro.status_http, erro.codigo, erro.mensagem, None)


app = criar_app()
