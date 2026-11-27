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
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from stur_api.agi.cliente import ClienteAgi
from stur_api.config import Configuracao
from stur_api.erros import ConsultaInvalida, ErroAplicacao, ErroInterno
from stur_api.registro import MiddlewareRegistro, configurar_registro
from stur_api.relogio import RelogioSistema
from stur_api.rotas import parametros, reservas, saude, vendas
from stur_api.rotas.desistencia import ClienteDesistiu
from stur_api.servicos.consultas import ServicoConsulta

PARAMETRO_INVALIDO = "parametro_invalido"
MENSAGEM_PARAMETRO_INVALIDO = "Um parâmetro da consulta está num formato inválido."
_ERROS_HTTP = {
    404: ("rota_inexistente", "Esta rota não existe nesta API."),
    405: ("metodo_nao_permitido", "Este método não é permitido nesta rota."),
}
_ERRO_HTTP_GENERICO = ("erro_http", "A requisição não pôde ser atendida.")


def criar_app(servico: ServicoConsulta | None = None) -> FastAPI:
    """Sem `servico`, o ciclo de vida monta o real a partir do ambiente (`Configuracao`).

    Aplica `configurar_registro()` aqui (idempotente), para que qualquer porta de entrada
    (uvicorn, testes) tenha os mesmos logs: uma linha `chave=valor`, httpx em WARNING.
    """
    configurar_registro()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        if servico is not None:
            yield
            return
        config = _ler_configuracao()
        relogio = RelogioSistema()
        async with httpx.AsyncClient(timeout=config.agi_tempo_limite_s) as http:
            app.state.servico = ServicoConsulta(config, ClienteAgi(config, http, relogio), relogio)
            yield

    app = FastAPI(
        title="stur-api",
        version="0.2.0",
        lifespan=ciclo_de_vida,
        generate_unique_id_function=_id_da_operacao,
    )
    if servico is not None:
        app.state.servico = servico
    app.add_middleware(MiddlewareRegistro)
    app.exception_handler(ErroAplicacao)(_erro_da_aplicacao)
    app.exception_handler(StarletteHTTPException)(_erro_http)
    app.exception_handler(RequestValidationError)(_parametro_invalido)
    app.exception_handler(ClienteDesistiu)(_cliente_desistiu)
    app.exception_handler(Exception)(_erro_inesperado)
    for modulo in (saude, parametros, vendas, reservas):
        app.include_router(modulo.roteador, prefix="/api/v1")
    return app


def _id_da_operacao(rota: APIRoute) -> str:
    """`operationId` = nome da função da rota (`consultar_vendas`): estável para os tipos."""
    return rota.name


def _ler_configuracao() -> Configuracao:
    """Configuração do ambiente; se inválida, o erro leva só nomes de campo e tipos de erro.

    O `ValidationError` original traz o valor recebido (senha, URL da AGI): fica de fora do
    log e do traceback (`from None`).
    """
    try:
        return Configuracao()
    except ValidationError as erro:
        problemas = [
            f"{'.'.join(str(parte) for parte in e['loc'])}: {e['type']}"
            for e in erro.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise RuntimeError(f"Configuração inválida: {', '.join(problemas)}") from None


def _resposta(status: int, codigo: str, mensagem: str, detalhe: Any, **extra: Any) -> JSONResponse:
    corpo = {"codigo": codigo, "mensagem": mensagem, "detalhe": detalhe, **extra}
    return JSONResponse(jsonable_encoder(corpo), status_code=status)


def _erro_da_aplicacao(_pedido: Request, erro: ErroAplicacao) -> JSONResponse:
    extra = {"campo": erro.campo} if isinstance(erro, ConsultaInvalida) else {}
    return _resposta(erro.status_http, erro.codigo, erro.mensagem, erro.detalhe, **extra)


def _erro_http(_pedido: Request, erro: StarletteHTTPException) -> JSONResponse:
    """404, 405 e demais erros HTTP no envelope; nunca o `detail` original."""
    codigo, mensagem = _ERROS_HTTP.get(erro.status_code, _ERRO_HTTP_GENERICO)
    resposta = _resposta(erro.status_code, codigo, mensagem, None)
    resposta.headers.update(erro.headers or {})
    return resposta


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


def _cliente_desistiu(_pedido: Request, _erro: ClienteDesistiu) -> Response:
    """Sem corpo: o cliente já saiu. O 499 (convenção do nginx) separa o caso no log."""
    return Response(status_code=499)


def _erro_inesperado(_pedido: Request, _erro: Exception) -> JSONResponse:
    erro = ErroInterno()
    return _resposta(erro.status_http, erro.codigo, erro.mensagem, None)


app = criar_app()
