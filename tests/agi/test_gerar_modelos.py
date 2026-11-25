import json
from pathlib import Path
from typing import Any

from gerar_modelos import gerar

DICIONARIO_MINIMO = (Path(__file__).parent / "dicionario_minimo.json").read_text(encoding="utf-8")


def test_gera_classe_aninhada_e_tipos() -> None:
    codigo = gerar(json.loads(DICIONARIO_MINIMO)["campos"])
    assert "class ServicoAgi(BaseModel):" in codigo
    assert "vlrTarifaTotal: Decimal | None = None" in codigo
    assert "detalheItem: list[ServicoAgi] | None = None" in codigo
    assert "'detalheItem[].vlrTarifaTotal'" in codigo  # em CAMINHOS_CONHECIDOS


def test_gerador_copia_so_nomes_e_tipos() -> None:
    codigo = gerar(json.loads(DICIONARIO_MINIMO)["campos"])
    for valor in (
        "CLIENTE EXEMPLO LTDA",
        "NOTA INVENTADA",
        "4321.98",
        "12.34",
        "2026-11-02",
        "1002",
    ):
        assert valor not in codigo


def test_origem_e_destino_usam_a_mesma_classe() -> None:
    codigo = gerar(json.loads(DICIONARIO_MINIMO)["campos"])
    assert codigo.count("class LocalTrechoAgi(BaseModel):") == 1
    assert "origem: LocalTrechoAgi | None = None" in codigo
    assert "destino: LocalTrechoAgi | None = None" in codigo
    assert "taxas: list[TaxaServicoAgi] | None = None" in codigo
    assert "camposGerenciais: list[Any] | None = None" in codigo
    assert "dtcancelamento: str | None = None" in codigo


def test_casos_de_borda_do_gerador() -> None:
    campos = {
        "soNulo": {"tipos": {"null": 2}},
        "valorMisto": {"tipos": {"int": 1, "float": 1}},
        "class": {"tipos": {"str": 1}},
        "json": {"tipos": {"str": 1}},
    }
    codigo = gerar(campos)
    assert "soNulo: Any = None" in codigo
    assert "valorMisto: Decimal | None = None" in codigo
    espaco: dict[str, Any] = {}
    exec(codigo, espaco)  # noqa: S102 (código gerado no próprio teste, sem entrada externa)
    venda = espaco["VendaAgi"].model_validate({"class": "A", "json": "B"})
    assert (venda.class_, venda.json_) == ("A", "B")
    assert espaco["CAMINHOS_CONHECIDOS"] == frozenset(campos)
