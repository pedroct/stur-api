"""Leitura das datas da AGI: texto local sem fuso, `T` ou espaço entre data e hora (PRD 8.2).

A hora `1899-12-30 00:00:00` é a data vazia do Stur e conta como ausente. Qualquer outro formato
é mudança da AGI e vira `api_stur_resposta_invalida`, nunca "sem data" em silêncio.
"""

from datetime import date, datetime, time

from stur_api.erros import ApiSturRespostaInvalida

DATA_VAZIA_DO_STUR = date(1899, 12, 30)
_TAMANHO = len("2026-11-17T08:05:09")


def ler_data_hora(texto: str | None, campo: str = "data") -> datetime | None:
    """Lê `AAAA-MM-DDTHH:MM:SS` ou `AAAA-MM-DD HH:MM:SS`, sem fuso.

    `None`, vazio e `1899-12-30…` viram `None`. Outro texto levanta `ApiSturRespostaInvalida`
    com o nome do campo e sem o valor.
    """
    if not texto:
        return None
    try:
        if len(texto) != _TAMANHO or texto[10] not in "T ":
            raise ValueError
        lido = datetime.strptime(texto[:10] + "T" + texto[11:], "%Y-%m-%dT%H:%M:%S")  # noqa: DTZ007
    except ValueError:
        # `from None`: a mensagem do ValueError traria o valor lido
        raise ApiSturRespostaInvalida(detalhe=[f"{campo}: formato_de_data_invalido"]) from None
    if lido.date() == DATA_VAZIA_DO_STUR:
        return None
    return lido


def tem_horario(valor: datetime | None) -> bool:
    """Verdadeiro quando a hora é diferente de 00:00:00 (meia-noite é "sem horário")."""
    return valor is not None and valor.time() != time(0, 0, 0)
