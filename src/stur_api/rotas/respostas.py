"""Erros que as rotas documentam no OpenAPI: o envelope real, não o `HTTPValidationError`."""

from typing import Any

from stur_api.contrato.comum import ErroApi, ErroConsulta

Respostas = dict[int | str, dict[str, Any]]

PARAMETRO_INVALIDO: Respostas = {
    422: {
        "model": ErroConsulta,
        "description": "Parâmetro inválido ou combinação inválida; `campo` aponta o primeiro.",
    }
}
ERROS_DA_AGI: Respostas = {
    500: {"model": ErroApi, "description": "Falha nesta aplicação, não na API do Stur."},
    502: {
        "model": ErroApi,
        "description": "A API do Stur recusou o acesso ou respondeu num formato desconhecido.",
    },
    504: {"model": ErroApi, "description": "A API do Stur não respondeu a tempo."},
}
VENDA_NAO_ENCONTRADA: Respostas = {
    404: {"model": ErroApi, "description": "Nenhuma venda com esse número e esse idreserva."}
}
