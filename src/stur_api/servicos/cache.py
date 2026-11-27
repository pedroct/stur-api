"""Resultado da lista guardado em memória por alguns minutos (PRD 9.3)."""

from collections import OrderedDict
from datetime import datetime, timedelta

from stur_api.contrato.consulta import ResultadoConsulta
from stur_api.dominio.consulta import ConsultaVendas
from stur_api.relogio import Relogio


class CacheResultados:
    """Chave: a `ConsultaVendas` inteira (R7). Vale `ttl_s` segundos pelo `relogio`; acima de
    `maximo` itens ou de `maximo_linhas` linhas no total, sai o guardado há mais tempo. Um
    resultado que sozinho passa de `maximo_linhas` não é guardado."""

    def __init__(
        self, ttl_s: int, relogio: Relogio, maximo: int = 50, maximo_linhas: int = 10_000
    ) -> None:
        self._validade = timedelta(seconds=ttl_s)
        self._relogio = relogio
        self._maximo = maximo
        self._maximo_linhas = maximo_linhas
        self._itens: OrderedDict[ConsultaVendas, tuple[datetime, ResultadoConsulta]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._itens)

    @property
    def linhas(self) -> int:
        """Total de linhas (vendas) dos resultados guardados."""
        return sum(len(valor.vendas) for _, valor in self._itens.values())

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
        # o que não cabe sozinho fica de fora, sem tirar os outros; o antigo da chave já saiu
        if len(valor.vendas) <= self._maximo_linhas:
            self._itens[chave] = (agora, valor)
        # A ordem de inserção é a ordem do tempo (guardar sempre reinsere no fim): os vencidos
        # ficam na frente e saem sem precisar de leitura.
        while self._itens:
            guardado_em, _ = next(iter(self._itens.values()))
            if agora - guardado_em < self._validade:
                break
            self._itens.popitem(last=False)
        while len(self._itens) > self._maximo or self.linhas > self._maximo_linhas:
            self._itens.popitem(last=False)
