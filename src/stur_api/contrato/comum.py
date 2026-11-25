"""Base do contrato: campos em camelCase pt-BR e `Decimal` como texto (roteiro, decisão 5)."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel


def _texto_decimal(valor: Decimal) -> str:
    """Notação fixa, com as casas que o valor tem: `Decimal("1E+5")` sai `"100000"`."""
    return format(valor, "f")


# Dinheiro, câmbio e percentuais: no JSON saem como texto decimal, sem passar por `float`.
DecimalTexto = Annotated[
    Decimal, PlainSerializer(_texto_decimal, return_type=str, when_used="json")
]


class Contrato(BaseModel):
    """Modelo de resposta: nome do Python em `snake_case`, nome no JSON em camelCase."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True
    )


SituacaoApiStur = Literal["ok", "sem_resposta", "acesso_recusado"]


class SaudeStur(Contrato):
    api_stur: SituacaoApiStur
