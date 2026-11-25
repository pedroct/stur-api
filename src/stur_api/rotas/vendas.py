"""`GET /api/v1/vendas`: resultado da consulta por número, período ou os dois."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from stur_api.contrato.consulta import ResultadoConsulta
from stur_api.dominio.consulta import Classificacao, ConsultaVendas, Situacao, TipoData
from stur_api.rotas.dependencias import obter_servico
from stur_api.rotas.respostas import ERROS_DA_AGI, PARAMETRO_INVALIDO
from stur_api.servicos.consultas import ServicoConsulta

roteador = APIRouter(responses={**PARAMETRO_INVALIDO, **ERROS_DA_AGI})


@roteador.get("/vendas")
async def consultar_vendas(
    *,
    servico: Annotated[ServicoConsulta, Depends(obter_servico)],
    reserva: int | None = None,
    tipo_data: Annotated[TipoData, Query(alias="tipoData")] = "emissao",
    de: date | None = None,
    ate: date | None = None,
    situacao: Annotated[list[Situacao], Query(default_factory=list)],
    classificacao: Annotated[list[Classificacao], Query(default_factory=list)],
    fornecedor: str | None = None,
    cliente: str | None = None,
    emissor: str | None = None,
    atualizar: bool = False,
) -> ResultadoConsulta:
    consulta = ConsultaVendas(
        reserva=reserva,
        tipo_data=tipo_data,
        de=de,
        ate=ate,
        situacoes=frozenset(situacao),
        classificacoes=frozenset(classificacao),
        fornecedor=fornecedor,
        cliente=cliente,
        emissor=emissor,
    )
    return await servico.consultar_vendas(consulta, atualizar)
