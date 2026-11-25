"""Saúde em duas rotas (roteiro, decisão 3): a do contêiner não depende da AGI."""

from typing import Annotated

from fastapi import APIRouter, Depends

from stur_api.contrato.comum import SaudeStur
from stur_api.rotas.dependencias import obter_servico
from stur_api.servicos.consultas import ServicoConsulta

roteador = APIRouter()


@roteador.get("/saude")
def saude() -> dict[str, str]:
    return {"aplicacao": "ok"}


@roteador.get("/saude/stur")
async def saude_stur(servico: Annotated[ServicoConsulta, Depends(obter_servico)]) -> SaudeStur:
    """Sempre 200: diz se a AGI aceita o login desta aplicação."""
    return SaudeStur(api_stur=await servico.verificar_api_stur())
