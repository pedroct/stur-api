"""Resultado da lista guardado em memória por alguns minutos (PRD 9.3)."""

from collections import OrderedDict
from datetime import datetime, timedelta

from stur_api.contrato.consulta import ResultadoConsulta
from stur_api.dominio.consulta import ConsultaVendas
from stur_api.relogio import Relogio


class CacheResultados:
    """Chave: a `ConsultaVendas` inteira (R7). Vale `ttl_s` segundos pelo `relogio`; acima de
    `maximo` itens, sai o guardado há mais tempo."""

    def __init__(self, ttl_s: int, relogio: Relogio, maximo: int = 50) -> None:
        self._validade = timedelta(seconds=ttl_s)
        self._relogio = relogio
        self._maximo = maximo
        self._itens: OrderedDict[ConsultaVendas, tuple[datetime, ResultadoConsulta]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._itens)

    def obter(self, chave: ConsultaVendas) -> ResultadoConsulta | None:
        item = self._itens.get(chave)
        if item is None:
            return None
        guardado_em, valor = item
        if self._relogio.agora() - guardado_em >= self._validade:
            del self._itens[chave]
            return None
        return valor

    def guardar(self, chave: ConsultaVendas, valor: ResultadoConsulta) -> None:
        agora = self._relogio.agora()
        self._itens.pop(chave, None)  # guardar de novo conta como o mais novo
        self._itens[chave] = (agora, valor)
        # A ordem de inserção é a ordem do tempo (guardar sempre reinsere no fim): os vencidos
        # ficam na frente e saem sem precisar de leitura.
        while self._itens:
            guardado_em, _ = next(iter(self._itens.values()))
            if agora - guardado_em < self._validade:
                break
            self._itens.popitem(last=False)
        while len(self._itens) > self._maximo:
            self._itens.popitem(last=False)
