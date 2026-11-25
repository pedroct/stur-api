"""AGI falsa para os testes (respx): login e `POST /api/reservas` respondendo pelo corpo do pedido.

O `agi` das fixtures expõe `login` e `reservas` (rotas respx: `call_count`, `calls`,
`side_effect`, `return_value`), a lista `vendas` que a AGI "tem" e `ultima_copia`, o
`dtalteracaovinculado` da venda devolvida pela consulta pequena por ALTERACAO (a que descobre a
data da cópia).
"""

import asyncio
import base64
import json
from typing import Any

import httpx
import respx

from stur_api.agi.json_cru import carregar_json
from stur_api.relogio import Relogio
from tests import fabrica

URL_FALSA = "https://agi.exemplo.invalid"
VALIDADE_TOKEN_S = 3600


def _base64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def jwt_falso(expira_em: float) -> str:
    """JWT sem assinatura válida; o cliente só lê o `exp` do payload."""
    cabecalho = _base64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _base64url(json.dumps({"sub": "usuario-de-teste", "exp": int(expira_em)}).encode())
    return f"{cabecalho}.{payload}.assinatura"


class RotaFalsa:
    """Rota respx cujo `return_value` vale de verdade: troca a resposta dinâmica padrão."""

    def __init__(self, rota: respx.Route) -> None:
        self._rota = rota

    def __getattr__(self, nome: str) -> Any:
        return getattr(self._rota, nome)

    @property
    def side_effect(self) -> Any:
        return self._rota.side_effect

    @side_effect.setter
    def side_effect(self, valor: Any) -> None:
        self._rota.side_effect = valor

    @property
    def return_value(self) -> httpx.Response | None:
        return self._rota.return_value

    @return_value.setter
    def return_value(self, resposta: httpx.Response) -> None:
        self._rota.side_effect = None
        self._rota.return_value = resposta


class AgiFalsa:
    def __init__(self, roteador: respx.MockRouter, relogio: Relogio) -> None:
        self._relogio = relogio
        self.vendas: list[dict[str, Any]] = [fabrica.venda()]
        self.ultima_copia: str | None = "2026-11-18 09:30:00"
        self.login = RotaFalsa(
            roteador.post(f"{URL_FALSA}/api/auth/login").mock(side_effect=self._responder_login)
        )
        self.reservas = RotaFalsa(
            roteador.post(f"{URL_FALSA}/api/reservas").mock(side_effect=self._responder_reservas)
        )

    async def _responder_login(self, _pedido: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.01)  # o login leva tempo: pedidos simultâneos se encontram na trava
        expira_em = self._relogio.agora().timestamp() + VALIDADE_TOKEN_S
        return httpx.Response(200, json={"token": jwt_falso(expira_em)})

    def _responder_reservas(self, pedido: httpx.Request) -> httpx.Response:
        corpo = carregar_json(pedido.content.decode())
        itens = corpo["ItensPorPagina"]
        if corpo["TipoData"] == "ALTERACAO" and itens == 100 and self.ultima_copia is not None:
            # consulta pequena que descobre a data da cópia: uma venda com a última alteração
            vendas = [fabrica.venda(dtalteracaovinculado=self.ultima_copia)]
        else:
            vendas = [v for v in self.vendas if _passa_nos_filtros(v, corpo)]
        inicio = (corpo["Pagina"] - 1) * itens
        return httpx.Response(
            200, text=fabrica.resposta_agi(vendas[inicio : inicio + itens], corpo["Pagina"])
        )


def _passa_nos_filtros(venda: dict[str, Any], corpo: dict[str, Any]) -> bool:
    if "Reserva" in corpo and venda.get("reserva") != corpo["Reserva"]:
        return False
    if "Id" in corpo and venda.get("idreserva") != corpo["Id"]:
        return False
    return "Status" not in corpo or str(venda.get("status")).upper() == str(corpo["Status"]).upper()
