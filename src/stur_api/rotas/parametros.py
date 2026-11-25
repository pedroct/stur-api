"""`GET /api/v1/parametros`: os parâmetros que a tela usa e até quando a API tem dados."""

from typing import Annotated

from fastapi import APIRouter, Depends

from stur_api.contrato.consulta import Parametros
from stur_api.rotas.dependencias import obter_servico
from stur_api.rotas.respostas import ERROS_DA_AGI
from stur_api.servicos.consultas import ServicoConsulta

roteador = APIRouter(responses=ERROS_DA_AGI)


@roteador.get("/parametros")
async def parametros(servico: Annotated[ServicoConsulta, Depends(obter_servico)]) -> Parametros:
    return await servico.parametros()
