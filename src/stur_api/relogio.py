from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

FUSO_HORARIO = ZoneInfo("America/Fortaleza")


class Relogio(Protocol):
    def agora(self) -> datetime: ...


class RelogioSistema:
    def agora(self) -> datetime:
        return datetime.now(FUSO_HORARIO)
