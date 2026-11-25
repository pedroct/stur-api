"""Leitura das datas da AGI: texto local sem fuso, `T` ou espaço entre data e hora (PRD 8.2).

A hora `1899-12-30 00:00:00` é a data vazia do Stur e conta como ausente.
"""

from datetime import date, datetime, time

DATA_VAZIA_DO_STUR = date(1899, 12, 30)


def ler_data_hora(texto: str | None) -> datetime | None:
    """Lê a data da AGI sem fuso; ausente, vazia ou `1899-12-30…` viram `None`."""
    if not texto:
        return None
    try:
        lido = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if lido.date() == DATA_VAZIA_DO_STUR:
        return None
    return lido


def tem_horario(valor: datetime | None) -> bool:
    """Verdadeiro quando a hora é diferente de 00:00:00 (meia-noite é "sem horário")."""
    return valor is not None and valor.time() != time(0, 0, 0)
