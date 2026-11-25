"""Dependências das rotas."""

from fastapi import Request

from stur_api.servicos.consultas import ServicoConsulta


def obter_servico(request: Request) -> ServicoConsulta:
    """O serviço que `criar_app` recebeu ou que o ciclo de vida montou."""
    servico: ServicoConsulta = request.app.state.servico
    return servico
