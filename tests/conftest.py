"""Fixtures compartilhadas. Cada task acrescenta a sua seção."""

from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta

import httpx
import pytest
import respx

from stur_api.agi.cliente import ClienteAgi
from stur_api.config import Configuracao
from stur_api.relogio import FUSO_HORARIO
from tests.agi_falsa import AgiFalsa


@pytest.fixture
def config() -> Configuracao:
    # _env_file=None: nos testes a configuração nunca lê o .env (em produção lê).
    return Configuracao(
        _env_file=None,
        stur_api_url="https://agi.exemplo.invalid",
        stur_api_usuario="usuario-de-teste",
        stur_api_senha="senha-de-teste",
    )


class RelogioFixo:
    """Relógio de teste: devolve o instante dado e só anda quando mandarem."""

    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def agora(self) -> datetime:
        return self._instante

    def avancar(self, segundos: float) -> None:
        self._instante += timedelta(seconds=segundos)


@pytest.fixture
def relogio() -> RelogioFixo:
    return RelogioFixo(datetime(2026, 11, 25, 10, 0, tzinfo=FUSO_HORARIO))


@pytest.fixture
def agi(relogio: RelogioFixo) -> Iterator[AgiFalsa]:
    with respx.mock(assert_all_called=False) as roteador:
        yield AgiFalsa(roteador, relogio)


@pytest.fixture
async def cliente(
    config: Configuracao, agi: AgiFalsa, relogio: RelogioFixo
) -> AsyncIterator[ClienteAgi]:
    async with httpx.AsyncClient() as http:
        yield ClienteAgi(config, http, relogio)
