"""Valores calculados no contrato: os dataclasses do domínio, com os mesmos campos em camelCase.

Os valores seguem como o domínio os entrega (da AGI, sem arredondar); `Decimal` sai como texto.
"""

from stur_api.contrato.comum import Contrato, DecimalTexto
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
