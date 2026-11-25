"""Logs: uma linha por evento, no formato `chave=valor`, sem dado pessoal.

Nunca entram no log: query string, corpo de pedido ou resposta, texto de filtro, nome de
cliente ou passageiro, URL da AGI, credenciais e tokens. A rota é o modelo (`/reservas/{numero}`),
nunca o caminho cru; rota não encontrada vira `rota=-`.
"""

import logging
import re
import sys
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_FORMATO = "ts=%(asctime)s nivel=%(levelname)s logger=%(name)s %(message)s"
_DATA = "%Y-%m-%dT%H:%M:%S%z"
_LOGGERS_SILENCIADOS = ("httpx", "httpcore")  # o INFO do httpx grava a URL da AGI (R9)
_METODOS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
_SO_DIGITOS = re.compile(r"[0-9]{1,18}")
_log = logging.getLogger("api.requisicao")


class _FiltroSemExcecao(logging.Filter):
    """Troca o traceback e a mensagem da exceção pelo NOME da classe.

    O uvicorn registra `Exception in ASGI application` com `exc_info` em `uvicorn.error`, e a
    mensagem da exceção (ou um `ValidationError` do pydantic, com `input_value`) pode carregar
    nome de cliente ou passageiro vindo da AGI. A linha do middleware já traz rota e status.
    """

    _stur_api = True

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info and record.exc_info[1] is not None:
            record.msg = "excecao_nao_tratada erro=%s"
            record.args = (type(record.exc_info[1]).__name__,)
            record.exc_info = None
            record.exc_text = None
        return True


def _instalar_filtro(destino: logging.Logger | logging.Handler) -> None:
    if not any(getattr(f, "_stur_api", False) for f in destino.filters):
        destino.addFilter(_FiltroSemExcecao())


def _rota(scope: Scope) -> str:
    """O modelo da rota com o prefixo dos roteadores (`/api/v1/reservas/{numero}`), ou `-`.

    `scope["route"].path` não traz o prefixo do `include_router`; ele é o que sobra do caminho
    pedido depois de tirar o trecho que a própria rota casou. Nunca sai o caminho pedido: o
    prefixo só existe se a rota casou, e então ele é configuração da aplicação.
    """
    rota = scope.get("route")
    modelo = getattr(rota, "path", None)
    if not isinstance(modelo, str):
        return "-"
    formato = getattr(rota, "path_format", modelo)
    try:
        trecho = formato.format_map(scope.get("path_params") or {})
    except (KeyError, IndexError, ValueError):
        return modelo
    pedido: str = scope.get("path", "")
    if trecho and pedido.endswith(trecho):
        return pedido[: len(pedido) - len(trecho)] + modelo
    return modelo


class _SaidaPadrao(logging.Handler):
    """Escreve em `sys.stderr` do momento (o stream pode ser trocado, como no pytest)."""

    _stur_api = True

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stderr.write(self.format(record) + "\n")
            sys.stderr.flush()
        except Exception:  # noqa: BLE001 — log nunca derruba a requisição
            self.handleError(record)


def configurar_registro(nivel: str = "INFO") -> None:
    """Configura a raiz com uma linha por evento. Idempotente.

    Nenhum traceback sai no log: só `excecao_nao_tratada erro=<Classe>` (ver `_FiltroSemExcecao`).
    Não toca em `uvicorn.access` (o Docker o desliga com `--no-access-log`; ele grava a query).
    """
    raiz = logging.getLogger()
    manipulador = next((h for h in raiz.handlers if getattr(h, "_stur_api", False)), None)
    if manipulador is None:
        manipulador = _SaidaPadrao()
        manipulador.setFormatter(logging.Formatter(_FORMATO, _DATA))
        raiz.addHandler(manipulador)
    _instalar_filtro(manipulador)  # o que propaga até a raiz com exc_info (asyncio, por exemplo)
    _instalar_filtro(logging.getLogger("uvicorn.error"))  # o handler do uvicorn é só dele
    raiz.setLevel(nivel.upper())
    for nome in _LOGGERS_SILENCIADOS:
        logging.getLogger(nome).setLevel(logging.WARNING)


def _parametro_numerico(scope: Scope, nome: str) -> str | None:
    """O parâmetro do caminho só vai ao log se for número: texto livre pode ser nome de gente."""
    valor = (scope.get("path_params") or {}).get(nome)
    return valor if isinstance(valor, str) and _SO_DIGITOS.fullmatch(valor) else None


class MiddlewareRegistro:
    """Uma linha por requisição HTTP: método, rota (modelo), número, idreserva, status e duração.

    ASGI puro: a exceção do handler continua subindo (a linha sai com status 500 e o nome da
    classe do erro, nunca a mensagem).
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        inicio = time.perf_counter()
        status: list[int] = []

        async def enviar(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                status.append(int(mensagem["status"]))
            await send(mensagem)

        erro: str | None = None
        try:
            await self._app(scope, receive, enviar)
        except BaseException as excecao:
            erro = type(excecao).__name__
            raise
        finally:
            self._registrar(scope, status[0] if status else 500, inicio, erro)

    @staticmethod
    def _registrar(scope: Scope, status: int, inicio: float, erro: str | None) -> None:
        metodo = scope.get("method", "")
        campos: list[tuple[str, Any]] = [
            ("metodo", metodo if metodo in _METODOS else "-"),
            ("rota", _rota(scope)),
        ]
        for nome in ("numero", "idreserva"):
            valor = _parametro_numerico(scope, nome)
            if valor is not None:
                campos.append((nome, valor))
        campos += [("status", status), ("duracao_ms", int((time.perf_counter() - inicio) * 1000))]
        if erro is not None:
            campos.append(("erro", erro))
        _log.info(" ".join(f"{k}={v}" for k, v in campos))
