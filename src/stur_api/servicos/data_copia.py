"""Até quando a API tem dados: o `dtalteracaovinculado` das vendas (roteiro, decisão 12).

A API serve uma cópia do Stur; todas as vendas trazem o instante da cópia nesse campo (PRD 8.7).
"""

from datetime import datetime, timedelta

import httpx

from stur_api.agi.campos import validar_venda
from stur_api.agi.cliente import ClienteAgi, FiltroAgi, janela_larga
from stur_api.agi.modelos import VendaAgi
from stur_api.dominio.datas import ler_data_hora
from stur_api.erros import ErroAplicacao
from stur_api.relogio import Relogio

_ITENS_DA_CONSULTA_PEQUENA = 100
# Com a AGI fora do ar, a consulta pequena só é tentada de novo depois disto (R18): sem isso,
# cada `/parametros` esperaria o tempo limite inteiro antes de responder.
_ESPERA_DEPOIS_DA_FALHA = timedelta(seconds=60)


class DataDaCopia:
    def __init__(self, cliente: ClienteAgi, relogio: Relogio, ttl_s: int) -> None:
        self._cliente = cliente
        self._relogio = relogio
        self._validade = timedelta(seconds=ttl_s)
        self._ultima: tuple[str, datetime] | None = None  # (data, quando foi vista)
        self._falhou_em: datetime | None = None  # última consulta pequena que falhou

    def registrar(self, vendas: list[VendaAgi]) -> str | None:
        """Maior `dtalteracaovinculado` das vendas, em ISO com `T`; passa a ser a última vista.

        Data em formato desconhecido levanta `ApiSturRespostaInvalida` (R16).
        """
        datas = [
            data
            for venda in vendas
            if (data := ler_data_hora(venda.dtalteracaovinculado, "dtalteracaovinculado"))
            is not None
        ]
        if not datas:
            return None
        maior = max(datas).isoformat()
        self._ultima = (maior, self._relogio.agora())
        return maior

    async def obter(self) -> str | None:
        """A última vista há menos de `ttl_s`; senão, uma consulta pequena. Falha → `None`.

        Depois de uma falha, devolve `None` sem chamar a AGI por 60 s.
        """
        agora = self._relogio.agora()
        if self._ultima is not None:
            data, vista_em = self._ultima
            if agora - vista_em < self._validade:
                return data
        if self._falhou_em is not None and agora - self._falhou_em < _ESPERA_DEPOIS_DA_FALHA:
            return None
        inicio, fim = janela_larga(self._cliente.config, agora.date())
        filtro = FiltroAgi(
            tipo_data="ALTERACAO",
            data_inicial=inicio,
            data_final=fim,
            itens_por_pagina=_ITENS_DA_CONSULTA_PEQUENA,
            so_primeira_pagina=True,
        )
        try:
            vendas = [validar_venda(v) for v in await self._cliente.buscar_vendas(filtro)]
            return self.registrar(vendas)
        except (ErroAplicacao, httpx.HTTPError):  # o cliente já traduz o httpx; por garantia
            self._falhou_em = self._relogio.agora()  # depois da espera, não antes
            return None  # sem a data, a tela só não mostra "Dados do Stur até …"
