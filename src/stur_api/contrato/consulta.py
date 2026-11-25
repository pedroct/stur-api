"""Contrato da consulta de vendas (`GET /api/v1/vendas`) e dos parâmetros da tela."""

from datetime import date

from pydantic import AwareDatetime

from stur_api.contrato.calculos import ResumoResultado, ResumoVenda
from stur_api.contrato.comum import Contrato
from stur_api.dominio.consulta import Classificacao, Situacao, TipoData


class ConsultaEcoada(Contrato):
    """Os parâmetros da consulta como o backend os entendeu."""

    reserva: int | None
    tipo_data: TipoData
    de: date | None
    ate: date | None
    situacao: list[Situacao]
    classificacao: list[Classificacao]
    fornecedor: str | None
    cliente: str | None
    emissor: str | None
    janela_larga: bool  # sem período: a AGI foi consultada na janela larga


class VinculoDoFee(Contrato):
    """A venda a que a linha de fee pertence; `produto` só quando ela está no resultado."""

    idreserva: int
    produto: str | None


class LinhaResultado(ResumoVenda):
    vendas_no_resultado: int  # linhas do resultado com o mesmo número de reserva
    fee: VinculoDoFee | None  # só na linha de fee


class ResultadoConsulta(Contrato):
    consulta: ConsultaEcoada
    consultado_em: AwareDatetime
    dados_do_stur_ate: str | None  # maior `dtalteracaovinculado`, ISO com `T`
    periodo_passa_da_copia: bool
    vendas: list[LinhaResultado]
    resumo: ResumoResultado


class Parametros(Contrato):
    periodo_maximo_dias: int
    linhas_por_pagina: int
    opcoes_por_pagina: list[int]
    tempo_limite_segundos: int
    dados_do_stur_ate: str | None
