"""Reserva, venda e dado cru (roteiro, decisão 2).

A rota da venda leva o número porque uma chamada à AGI pelo filtro `Reserva` já traz a venda,
as outras vendas do número e o fee. Nenhuma das três guarda resultado (PRD RF-10).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from stur_api.contrato.venda import ReservaConsultada, VendaConsultada
from stur_api.rotas.dependencias import obter_servico
from stur_api.servicos.consultas import ServicoConsulta

roteador = APIRouter()

Servico = Annotated[ServicoConsulta, Depends(obter_servico)]

_DADO_CRU: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "A venda como a AGI devolveu: números exatos e a ordem das chaves.",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
}


@roteador.get("/reservas/{numero}")
async def abrir_reserva(numero: int, servico: Servico) -> ReservaConsultada:
    """Número sem vendas: 200 com `reserva.vendas` vazia."""
    return await servico.abrir_reserva(numero)


@roteador.get("/reservas/{numero}/vendas/{idreserva}")
async def abrir_venda(numero: int, idreserva: int, servico: Servico) -> VendaConsultada:
    """`idreserva` fora do número: 404 `venda_nao_encontrada`."""
    return await servico.abrir_venda(numero, idreserva)


@roteador.get(
    "/reservas/{numero}/vendas/{idreserva}/dado-cru", response_class=Response, responses=_DADO_CRU
)
async def dado_cru(numero: int, idreserva: int, servico: Servico) -> Response:
    texto = await servico.dado_cru(numero, idreserva)
    return Response(content=texto, media_type="application/json")
