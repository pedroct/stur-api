"""Cliente da AGI do Stur: login com token em memória, busca paginada e erros traduzidos."""

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx

from stur_api.agi.json_cru import carregar_json
from stur_api.config import Configuracao
from stur_api.erros import (
    ApiSturAcessoRecusado,
    ApiSturRespostaInvalida,
    ApiSturSemResposta,
    ErroAplicacao,
)
from stur_api.relogio import Relogio

# Os logs nunca levam URL, credenciais, token, corpo nem texto de filtro (cliente, fornecedor...).
_log = logging.getLogger("agi.reservas")
_log_login = logging.getLogger("agi.login")

MAX_PAGINAS = 50
VALIDADE_SEM_EXP = timedelta(minutes=55)
FOLGA_RENOVACAO = timedelta(seconds=60)
CHAVES_DO_TOKEN = ("token", "accesstoken", "access_token", "jwt", "bearer")


@dataclass(frozen=True)
class FiltroAgi:
    tipo_data: Literal["EMISSAO", "CONFIRMACAO", "ALTERACAO"]
    data_inicial: date
    data_final: date
    reserva: int | None = None
    id: int | None = None
    status: str | None = None
    itens_por_pagina: int = 100
    so_primeira_pagina: bool = False


@dataclass(frozen=True)
class _FalhaDeLogin:
    """O que se guarda de um login que falhou: nunca a exceção, cujo traceback (e contexto)
    manteria a senha na memória."""

    classe: type[ErroAplicacao]
    codigo: str
    mensagem: str
    detalhe: Any

    @classmethod
    def de(cls, erro: ErroAplicacao) -> "_FalhaDeLogin":
        return cls(type(erro), erro.codigo, erro.mensagem, erro.detalhe)

    def novo_erro(self) -> ErroAplicacao:
        """Um erro novo, igual ao original."""
        # cada classe tem o seu construtor: monta pelo da base, com os dados já prontos
        erro = self.classe.__new__(self.classe)
        ErroAplicacao.__init__(erro, self.codigo, self.mensagem, self.detalhe)
        return erro


@dataclass(frozen=True)
class _TentativaDeLogin:
    quando: datetime  # quando o resultado chegou
    falha: _FalhaDeLogin | None  # None: o login deu certo


def _corpo_da_busca(filtro: FiltroAgi, pagina: int) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "Pagina": pagina,
        "ItensPorPagina": filtro.itens_por_pagina,
        "TipoData": filtro.tipo_data,
        "DataInicial": filtro.data_inicial.isoformat(),
        "DataFinal": filtro.data_final.isoformat(),
    }
    if filtro.reserva is not None:
        corpo["Reserva"] = filtro.reserva
    if filtro.id is not None:
        corpo["Id"] = filtro.id
    if filtro.status is not None:
        corpo["Status"] = filtro.status
    return corpo


def _extrair_token(texto: str) -> str | None:
    """Token no JSON (chave sem diferença de caixa), JSON string ou JWT puro no corpo."""
    try:
        dados = carregar_json(texto)
    except ValueError:
        dados = texto.strip()
        return dados if dados.count(".") == 2 and " " not in dados else None
    if isinstance(dados, str):
        return dados or None
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            if str(chave).lower() in CHAVES_DO_TOKEN and isinstance(valor, str) and valor:
                return valor
    return None


def _expiracao_do_jwt(token: str) -> datetime | None:
    """Instante do `exp` do JWT (payload base64url, assinatura não verificada), se houver."""
    partes = token.split(".")
    if len(partes) != 3:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(partes[1] + "=" * (-len(partes[1]) % 4)))
        exp = payload["exp"]
        if isinstance(exp, bool) or not isinstance(exp, int | float):
            return None
        return datetime.fromtimestamp(exp, tz=ZoneInfo("UTC"))
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, OSError):
        # `exp` fora do alcance do datetime (1e30): OverflowError/OSError; vale a regra de 55 min
        return None


class ClienteAgi:
    def __init__(self, config: Configuracao, http: httpx.AsyncClient, relogio: Relogio) -> None:
        self._config = config
        self._http = http
        self._relogio = relogio
        self._token: str | None = None
        self._expira_em: datetime | None = None
        self._ultimo_login: _TentativaDeLogin | None = None
        self._trava_login = asyncio.Lock()

    @property
    def config(self) -> Configuracao:
        """Configuração do acesso à AGI (janela larga, itens por página, tempo limite)."""
        return self._config

    async def verificar_acesso(self) -> None:
        """Prova que as credenciais valem com um login de verdade (não reaproveita o token), no
        máximo um por intervalo: dentro dele, repete o resultado da última tentativa."""
        async with self._trava_login:
            recente = self._login_recente()
            if recente is None:
                await self._entrar()
            elif recente.falha is not None:
                raise recente.falha.novo_erro()

    async def buscar_vendas(self, filtro: FiltroAgi) -> list[dict[str, Any]]:
        vendas: list[dict[str, Any]] = []
        for pagina in range(1, MAX_PAGINAS + 1):
            itens = await self._buscar_pagina(filtro, pagina)
            vendas.extend(itens)
            if filtro.so_primeira_pagina or len(itens) < filtro.itens_por_pagina:
                return vendas
        raise ApiSturRespostaInvalida(
            detalhe={"erro": f"A consulta passou de {MAX_PAGINAS} páginas.", "paginas": MAX_PAGINAS}
        )

    # --- token ---

    def _token_vale(self) -> bool:
        return (
            self._token is not None
            and self._expira_em is not None
            and self._expira_em - self._relogio.agora() >= FOLGA_RENOVACAO
        )

    async def _token_valido(self, recusado: str | None = None) -> str:
        """Token em uso; faz login se faltar menos de 60 s ou se a AGI recusou o `recusado`."""
        if self._token is not None and self._token != recusado and self._token_vale():
            return self._token
        async with self._trava_login:
            # outro pedido pode ter feito o login enquanto este esperava a trava
            if self._token is not None and self._token != recusado and self._token_vale():
                return self._token
            return await self._entrar()

    def _login_recente(self) -> _TentativaDeLogin | None:
        """A última tentativa, se feita há menos que o intervalo. Quem chama segura a trava."""
        ultimo = self._ultimo_login
        intervalo = timedelta(seconds=self._config.agi_intervalo_login_s)
        if ultimo is None or self._relogio.agora() - ultimo.quando >= intervalo:
            return None
        return ultimo

    async def _entrar(self) -> str:
        """Login, com o resultado registrado. Quem chama segura `_trava_login`. Depois de uma
        recusa, repete a recusa sem chamar a AGI até o intervalo passar."""
        recente = self._login_recente()
        falha = None if recente is None else recente.falha
        if falha is not None and issubclass(falha.classe, ApiSturAcessoRecusado):
            raise falha.novo_erro()
        tentativa = asyncio.create_task(self._tentar_login())
        try:
            return await asyncio.shield(tentativa)
        except asyncio.CancelledError:
            # quem desistiu não corta o login já enviado: a trava fica presa até ele terminar e
            # o resultado é registrado, senão o próximo faria outro login dentro do intervalo
            await asyncio.wait([tentativa])
            if not tentativa.cancelled():
                tentativa.exception()  # já registrada; lida para o asyncio não a imprimir
            raise

    async def _tentar_login(self) -> str:
        try:
            token = await self._fazer_login()
        except ErroAplicacao as erro:
            self._ultimo_login = _TentativaDeLogin(self._relogio.agora(), _FalhaDeLogin.de(erro))
            raise
        self._ultimo_login = _TentativaDeLogin(self._relogio.agora(), None)
        return token

    async def _fazer_login(self) -> str:
        corpo = {
            "Username": self._config.stur_api_usuario,
            "Password": self._config.stur_api_senha.get_secret_value(),
        }
        inicio = time.perf_counter()
        status: int | str = "falhou"
        try:
            resposta = await self._enviar("/api/auth/login", corpo, {})
            status = resposta.status_code
        finally:
            _log_login.info("login status=%s duracao_ms=%d", status, _ms(inicio))
        if resposta.status_code in (400, 401, 403):
            raise ApiSturAcessoRecusado(detalhe={"status": resposta.status_code})
        self._exigir_sucesso(resposta)
        token = _extrair_token(resposta.text)
        if token is None:
            raise ApiSturRespostaInvalida(detalhe={"erro": "O login não devolveu o token."})
        expira = _expiracao_do_jwt(token)
        self._token = token
        self._expira_em = expira if expira is not None else self._relogio.agora() + VALIDADE_SEM_EXP
        return token

    # --- busca ---

    async def _buscar_pagina(self, filtro: FiltroAgi, pagina: int) -> list[dict[str, Any]]:
        corpo = _corpo_da_busca(filtro, pagina)
        inicio = time.perf_counter()
        status: int | str = "falhou"
        quantidade: int | str = "-"
        try:
            token = await self._token_valido()
            resposta = await self._pedir_reservas(corpo, token)
            if resposta.status_code == 401:
                token = await self._token_valido(recusado=token)
                resposta = await self._pedir_reservas(corpo, token)
            status = resposta.status_code
            if status == 401:
                raise ApiSturAcessoRecusado(detalhe={"status": 401})
            if status == 400:
                raise ApiSturRespostaInvalida(detalhe=_erro_da_agi(resposta))
            self._exigir_sucesso(resposta)
            itens = self._ler_lista(resposta)
            quantidade = len(itens)
            return itens
        finally:
            _log.info(
                "buscar_vendas tipo_data=%s inicio=%s fim=%s reserva=%s id=%s pagina=%d "
                "quantidade=%s status=%s duracao_ms=%d",
                filtro.tipo_data,
                filtro.data_inicial,
                filtro.data_final,
                filtro.reserva,
                filtro.id,
                pagina,
                quantidade,
                status,
                _ms(inicio),
            )

    async def _pedir_reservas(self, corpo: dict[str, Any], token: str) -> httpx.Response:
        return await self._enviar("/api/reservas", corpo, {"Authorization": f"Bearer {token}"})

    async def _enviar(
        self, rota: str, corpo: dict[str, Any], cabecalhos: dict[str, str]
    ) -> httpx.Response:
        limite = self._config.agi_tempo_limite_s
        try:
            return await self._http.post(
                f"{self._config.stur_api_url.rstrip('/')}{rota}",
                json=corpo,
                headers=cabecalhos,
                timeout=limite,
            )
        except httpx.TimeoutException:
            raise ApiSturSemResposta(limite, detalhe={"motivo": "tempo_esgotado"}) from None
        except httpx.TransportError as erro:
            raise ApiSturSemResposta(limite, detalhe={"motivo": type(erro).__name__}) from None
        except httpx.HTTPError as erro:
            # o que sobra do httpx (corpo que não decodifica, redirecionamentos demais...): a AGI
            # respondeu algo que não serve. O erro original pode trazer a URL, que não vai ao log.
            raise ApiSturRespostaInvalida(detalhe={"erro": type(erro).__name__}) from None

    def _exigir_sucesso(self, resposta: httpx.Response) -> None:
        if resposta.status_code >= 500:
            raise ApiSturSemResposta(
                self._config.agi_tempo_limite_s, detalhe={"status": resposta.status_code}
            )
        if resposta.status_code != 200:
            raise ApiSturRespostaInvalida(detalhe={"status": resposta.status_code})

    def _ler_lista(self, resposta: httpx.Response) -> list[dict[str, Any]]:
        try:
            dados = carregar_json(resposta.text)
        except ValueError:
            raise ApiSturRespostaInvalida(detalhe={"erro": "A resposta não é JSON."}) from None
        lista = dados.get("vendas", dados.get("Vendas")) if isinstance(dados, dict) else None
        if not isinstance(lista, list):
            raise ApiSturRespostaInvalida(
                detalhe={"erro": "A resposta não traz a lista de vendas."}
            )
        return lista


def _ms(inicio: float) -> int:
    return round((time.perf_counter() - inicio) * 1000)


def _erro_da_agi(resposta: httpx.Response) -> dict[str, Any]:
    """`Erro` e `Detalhes` do 400 da AGI; nunca o corpo inteiro."""
    try:
        dados = carregar_json(resposta.text)
    except ValueError:
        dados = None
    if not isinstance(dados, dict):
        return {"erro": None, "detalhes": None}
    return {"erro": dados.get("Erro"), "detalhes": dados.get("Detalhes")}


def janela_larga(config: Configuracao, hoje: date) -> tuple[date, date]:
    """Janela larga da consulta só por número: do início configurado ao fim do ano seguinte."""
    return config.janela_inicio, config.janela_fim(hoje)
