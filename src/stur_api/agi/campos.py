"""Campos da venda da AGI: o que conta como preenchido, campos desconhecidos e validação."""

from typing import Any

from pydantic import ValidationError

from stur_api.agi.modelos import CAMINHOS_CONHECIDOS, VendaAgi
from stur_api.erros import ApiSturRespostaInvalida


def preenchido(valor: Any) -> bool:
    """Falso só para `None`, `""`, `[]` e `{}`; zero e `False` são dados (PRD RF-04)."""
    if valor is None:
        return False
    if isinstance(valor, str | list | dict):
        return len(valor) > 0
    return True


def campos_desconhecidos(venda_cru: dict[str, Any]) -> list[str]:
    """Caminhos de folha preenchidos fora de `CAMINHOS_CONHECIDOS`, em ordem.

    Índices de lista viram `[]`: `detalheItem[].taxaNova`.
    """
    encontrados: set[str] = set()
    _procurar(venda_cru, "", encontrados)
    return sorted(encontrados)


def _procurar(objeto: dict[str, Any], prefixo: str, encontrados: set[str]) -> None:
    for nome, valor in objeto.items():
        caminho = prefixo + nome
        if isinstance(valor, dict):
            _procurar(valor, caminho + ".", encontrados)
            continue
        if isinstance(valor, list):
            itens = [item for item in valor if isinstance(item, dict)]
            for item in itens:
                _procurar(item, caminho + "[].", encontrados)
            if len(itens) == len(valor):
                continue  # lista de objetos (ou vazia): as folhas são os campos dos itens
        if preenchido(valor) and caminho not in CAMINHOS_CONHECIDOS:
            encontrados.add(caminho)


def validar_venda(venda_cru: dict[str, Any]) -> VendaAgi:
    """Valida a venda crua no modelo gerado: campo ausente vira `None`, tipo errado vira erro.

    O `detalhe` do erro traz `"caminho: tipo do erro"` e nunca o valor recebido, que pode ser
    dado pessoal. Sem `idreserva` ou sem `reserva` a venda não pode ser aberta.
    """
    try:
        venda = VendaAgi.model_validate(venda_cru)
    except ValidationError as erro:
        detalhe = [
            f"{_caminho(e['loc'])}: {e['type']}"
            for e in erro.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise ApiSturRespostaInvalida(detalhe=detalhe) from None  # o erro original tem o valor
    faltam = [
        f"{nome}: missing"
        for nome, valor in (("idreserva", venda.idreserva), ("reserva", venda.reserva))
        if valor is None
    ]
    if faltam:
        raise ApiSturRespostaInvalida(detalhe=faltam)
    return venda


def _caminho(loc: tuple[int | str, ...]) -> str:
    """`("detalheItem", 1, "vlrTarifaTotal")` → `"detalheItem[1].vlrTarifaTotal"`."""
    texto = ""
    for parte in loc:
        if isinstance(parte, int):
            texto += f"[{parte}]"
        else:
            texto += f".{parte}" if texto else parte
    return texto
