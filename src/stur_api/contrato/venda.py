"""Contrato da reserva (`GET /api/v1/reservas/{numero}`) e da venda (`.../vendas/{idreserva}`).

A venda sai com os nomes da AGI (roteiro, decisão 4); os valores calculados e os envelopes, em
camelCase pt-BR. Dinheiro, câmbio e percentuais como texto em toda parte, também dentro da venda.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, PlainSerializer

from stur_api.agi.modelos import VendaAgi
from stur_api.contrato.calculos import (
    ContaServico,
    EstadoServico,
    Itinerario,
    LancamentoCalculado,
    ResumoVenda,
    TotaisReserva,
    Verificacao,
)
from stur_api.contrato.comum import Contrato, DecimalTexto, decimais_em_texto
from stur_api.dominio.vendas import TipoVenda

# A venda como a AGI mandou: campos com os nomes dela, ausente como `null`, campo novo mantido
# (o modelo aceita extras) e datas como vieram. A função de serialização não tem anotação de
# retorno de propósito (lambda): assim o OpenAPI continua descrevendo `VendaAgi` campo a campo,
# e não um objeto qualquer.
VendaDaAgi = Annotated[
    VendaAgi,
    PlainSerializer(lambda venda: decimais_em_texto(venda.model_dump()), when_used="json"),
]

CodigoAviso = Literal[
    "conta_nao_fecha",
    "moeda_estrangeira",
    "moeda_cambio_1",
    "comissao_nao_apurada",
    "venda_fee",
    "venda_cancelada",
    "venda_reservada",
]


class VendaDaReserva(Contrato):
    resumo: ResumoVenda
    posicao: int  # 1 a n, na ordem de lançamento
    recebimentos: list[LancamentoCalculado]
    pagamentos: list[LancamentoCalculado]


class Reserva(Contrato):
    numero: int
    vendas: list[VendaDaReserva]  # na ordem de lançamento
    totais: TotaisReserva


class ReservaConsultada(Contrato):
    numero: int
    consultado_em: AwareDatetime
    dados_do_stur_ate: str | None  # maior `dtalteracaovinculado`, ISO com `T`
    reserva: Reserva  # número sem vendas: `vendas` vazia (tela 13 é estado, não erro)


class TotaisServicos(Contrato):
    """Soma das contas dos serviços (a coluna da lista de serviços), não os totais da API."""

    cliente: DecimalTexto
    fornecedor: DecimalTexto
    margem: DecimalTexto
    percentual_lucro: DecimalTexto | None


class Aviso(Contrato):
    codigo: CodigoAviso
    siglas: list[str]  # nos avisos de moeda: as siglas como a AGI escreve; nos outros, vazia


class CalculosVenda(Contrato):
    tipo: TipoVenda
    servicos: list[ContaServico]
    totais_servicos: TotaisServicos
    percentual_lucro: DecimalTexto | None  # da venda: `margemLucroBruta` ÷ `totalCliente`
    verificacao: Verificacao
    recebimentos: list[LancamentoCalculado]
    pagamentos: list[LancamentoCalculado]
    total_pagamentos: DecimalTexto  # Σ demais formas − Σ crédito
    # total dos pagamentos − `totalFornecedor`; negativo é pagamento ainda não lançado (PRD 8.3)
    diferenca_pagamentos_fornecedor: DecimalTexto
    itinerario: Itinerario | None
    estado_servico: EstadoServico | None
    avisos: list[Aviso]  # atenção antes de informação (IA 9.5)


class VendaVinculada(Contrato):
    """Outra venda ligada a esta. `posicao` e `quantidade` só quando ela é do mesmo número."""

    idreserva: int
    numero: int
    produto: str | None
    posicao: int | None
    quantidade: int | None  # vendas do número da vinculada


class ReembolsoVinculado(Contrato):
    id: int | None
    numero_sr: str | None = Field(alias="numeroSR")  # o nome da AGI
    nome_pax: str | None
    venda: VendaVinculada | None  # `null` se a venda não foi achada ou a busca falhou


class Vinculos(Contrato):
    fee: VendaVinculada | None  # a outra ponta do vínculo de fee, do mesmo número (PRD 8.4)
    reembolsos: list[ReembolsoVinculado]


class VendaConsultada(Contrato):
    consultado_em: AwareDatetime
    dados_do_stur_ate: str | None
    venda: VendaDaAgi
    calculos: CalculosVenda
    reserva: Reserva
    posicao: int
    vinculos: Vinculos
    campos_desconhecidos: list[str]
