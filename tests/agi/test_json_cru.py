from decimal import Decimal

from stur_api.agi.json_cru import carregar_json, serializar_cru


def test_numeros_viram_decimal_exatos() -> None:
    dados = carregar_json('{"valor": 150197.72, "cambio": 1.000000000}')
    assert dados["valor"] == Decimal("150197.72")
    assert isinstance(dados["valor"], Decimal)


def test_dado_cru_preserva_literais_e_ordem() -> None:
    texto = (
        '{"z": 150197.72, "a": 1.000000000, "b": 0.0, "c": -13620.74, '
        '"d": "AÇÃO", "e": null, "f": false}'
    )
    saida = serializar_cru(carregar_json(texto))
    for literal in ("150197.72", "1.000000000", "0.0", "-13620.74", '"AÇÃO"', "null", "false"):
        assert literal in saida
    assert saida.index('"z"') < saida.index('"a"')
