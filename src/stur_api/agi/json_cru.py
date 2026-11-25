"""Leitura e escrita do JSON da AGI sem perder casas decimais."""

import json
from decimal import Decimal
from typing import Any

import simplejson


def carregar_json(texto: str) -> Any:
    """Lê o JSON da AGI com todo número decimal como `Decimal` exato."""
    return json.loads(texto, parse_float=Decimal)


def serializar_cru(valor: Any) -> str:
    """Escreve o dado cru fiel: `Decimal` como número, ordem das chaves mantida."""
    return simplejson.dumps(valor, use_decimal=True, ensure_ascii=False, indent=2)
