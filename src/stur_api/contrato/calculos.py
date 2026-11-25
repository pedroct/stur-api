"""Valores calculados no contrato: os dataclasses do domínio, com os mesmos campos em camelCase.

Os valores seguem como o domínio os entrega (da AGI, sem arredondar); `Decimal` sai como texto.
"""

from datetime import date
from typing import Literal

from stur_api.contrato.comum import Contrato, DecimalTexto
from stur_api.dominio.contas import Efeito
from stur_api.dominio.estado_servico import Base, Estado
from stur_api.dominio.itinerario import Forma
from stur_api.dominio.lancamentos import SituacaoLancamento
from stur_api.dominio.vendas import TipoVenda


class ResumoVenda(Contrato):
    numero: int | None
    idreserva: int | None
    produto: str | None
    classificacao: str | None
    categoria: str | None
    cliente: str | None
    fornecedor: str | None
    fornecedor2: str | None
    emissor: str | None
    data_emissao: str | None  # datas da AGI como vieram (texto local sem fuso)
    data_confirmacao: str | None
    data_alteracao: str | None
    situacao: str | None  # `status` da AGI em minúsculas: "fechada", "cancelada"...
    total_cliente: DecimalTexto
    total_fornecedor: DecimalTexto
    margem: DecimalTexto
    percentual_lucro: DecimalTexto | None
    conta_fecha: bool
    tipo: TipoVenda
    id_venda_fee: int | None  # na venda comum: a venda de fee ligada a ela
    passageiros: list[str]


class ResumoIncentivos(Contrato):
    quantidade: int
    valor: DecimalTexto
    margem_com_incentivos: DecimalTexto
    percentual_com_incentivos: DecimalTexto | None


class ResumoResultado(Contrato):
    quantidade: int  # vendas a cliente, sem canceladas e sem incentivos
    total_cliente: DecimalTexto
    total_fornecedor: DecimalTexto
    margem: DecimalTexto
    percentual_lucro: DecimalTexto | None
    nao_fecham: int
    canceladas: int
    incentivos: ResumoIncentivos


class TotaisReserva(Contrato):
    quantidade: int  # todas as vendas, canceladas incluídas
    quantidade_canceladas: int
    total_cliente: DecimalTexto  # só as não canceladas
    total_fornecedor: DecimalTexto
    margem: DecimalTexto
    percentual_lucro: DecimalTexto | None


# --- conta de cada serviço e verificação dos totais (PRD 8.3, RF-06) ---


class TermoConta(Contrato):
    campo: str  # nome do campo na AGI
    valor: DecimalTexto  # a tarifa já multiplicada pelo câmbio
    efeito: Efeito


class Conversao(Contrato):
    sigla: str
    tarifa_origem: DecimalTexto
    cambio: DecimalTexto
    data_cambio: str | None  # data da AGI como veio


class ContaLado(Contrato):
    termos: list[TermoConta]
    zerados: list[str]  # campos da AGI zerados neste serviço
    total: DecimalTexto
    conversao: Conversao | None
    sigla_com_cambio_1: str | None


class ContaServico(Contrato):
    indice: int  # posição do serviço em `detalheItem`
    cliente: ContaLado
    fornecedor: ContaLado
    margem: DecimalTexto
    percentual_lucro: DecimalTexto | None
    comissoes_nao_apuradas: bool


class ContaVerificada(Contrato):
    conta: Literal["cliente", "fornecedor", "margem"]
    calculado: DecimalTexto
    api: DecimalTexto
    diferenca: DecimalTexto  # calculado − api
    fecha: bool


class Verificacao(Contrato):
    contas: list[ContaVerificada]
    tolerancia: DecimalTexto
    fecha: bool


# --- lançamentos, itinerário e estado do serviço ---


class LancamentoCalculado(Contrato):
    indice: int  # posição na lista da AGI (`recebimentos` ou `pagamentos`)
    valor_exibido: DecimalTexto
    eh_credito: bool
    situacao: SituacaoLancamento
    vencido: bool
    cartao_repassado: bool


class Espera(Contrato):
    apos_trecho: int  # índice do trecho em `trechos`
    minutos: int
    aeroporto: str


class Trajeto(Contrato):
    trechos: list[int]
    esperas: list[Espera]


class Estadia(Contrato):
    apos_trajeto: int  # posição do trajeto na lista de trajetos
    dias: int
    sigla: str
    cidade: str | None


class Itinerario(Contrato):
    forma: Forma
    trajetos: list[Trajeto]
    estadias: list[Estadia]


class EstadoServico(Contrato):
    estado: Estado
    inicio: date
    fim: date
    base: Base
