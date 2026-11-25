"""Consulta de vendas: pedido do usuário, validação e filtro enviado à AGI (PRD 8.2, RF-01)."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from stur_api.agi.cliente import FiltroAgi, janela_larga
from stur_api.config import Configuracao
from stur_api.erros import ConsultaInvalida

Situacao = Literal["reservada", "confirmada", "fechada", "cancelada"]
Classificacao = Literal["aereo", "hotelaria", "rodoviario", "diversos", "locacao", "pacote"]
TipoData = Literal["emissao", "confirmacao", "alteracao"]

_TIPO_DATA_AGI: dict[TipoData, Literal["EMISSAO", "CONFIRMACAO", "ALTERACAO"]] = {
    "emissao": "EMISSAO",
    "confirmacao": "CONFIRMACAO",
    "alteracao": "ALTERACAO",
}
_ITENS_POR_PAGINA_COM_NUMERO = 100


@dataclass(frozen=True)
class ConsultaVendas:
    """Pedido de consulta. Imutável e hashável: serve de chave do cache."""

    reserva: int | None
    tipo_data: TipoData = "emissao"
    de: date | None = None
    ate: date | None = None
    situacoes: frozenset[Situacao] = frozenset()
    classificacoes: frozenset[Classificacao] = frozenset()
    fornecedor: str | None = None
    cliente: str | None = None
    emissor: str | None = None


def validar_consulta(c: ConsultaVendas, config: Configuracao) -> None:
    """Levanta `ConsultaInvalida` na primeira regra quebrada. Com número, período longo passa."""
    if c.reserva is None and c.de is None and c.ate is None:
        raise ConsultaInvalida(
            "consulta_vazia",
            "Digite o número da reserva, escolha um período ou os dois.",
            "reserva",
        )
    if (c.de is None) != (c.ate is None):
        raise ConsultaInvalida(
            "periodo_incompleto",
            "Preencha as duas datas do período.",
            "ate" if c.ate is None else "de",
        )
    if c.de is None or c.ate is None:
        return
    if c.ate < c.de:
        raise ConsultaInvalida("periodo_invertido", "A data final é anterior à inicial.", "ate")
    maximo = config.periodo_maximo_dias
    if c.reserva is None and (c.ate - c.de).days + 1 > maximo:
        raise ConsultaInvalida(
            "periodo_longo",
            f"Sem número de reserva, o período vai até {maximo} dias. "
            "Diminua o período ou informe o número.",
            "de",
        )


def filtro_agi(c: ConsultaVendas, config: Configuracao, hoje: date) -> FiltroAgi:
    """Filtro enviado à AGI. O que ela não filtra (ou filtra mal) fica para `aplicar_filtros`."""
    if c.de is None or c.ate is None:
        inicio, fim = janela_larga(config, hoje)
        tipo_data = _TIPO_DATA_AGI["emissao"]
    else:
        inicio, fim = c.de, c.ate
        tipo_data = _TIPO_DATA_AGI[c.tipo_data]
    status = next(iter(c.situacoes)).upper() if len(c.situacoes) == 1 else None
    return FiltroAgi(
        tipo_data=tipo_data,
        data_inicial=inicio,
        data_final=fim,
        reserva=c.reserva,
        status=status,
        itens_por_pagina=(
            _ITENS_POR_PAGINA_COM_NUMERO if c.reserva is not None else config.agi_itens_por_pagina
        ),
    )
