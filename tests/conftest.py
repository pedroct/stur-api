"""Fixtures compartilhadas. Cada task acrescenta a sua seção."""

from datetime import datetime, timedelta

import pytest

from stur_api.config import Configuracao


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
