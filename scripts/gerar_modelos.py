"""Gera `src/stur_api/agi/modelos.py` a partir do dicionário de campos da AGI.

Uso:
    uv run python scripts/gerar_modelos.py <dicionario_campos.json> > src/stur_api/agi/modelos.py
    uv run ruff format src/stur_api/agi/modelos.py

Lê só a chave `campos` (caminho → `tipos`). Copia nomes e tipos, nunca `valores` nem `nota`:
o dicionário vem de dados reais e o repositório é público. A saída é determinística (mesma
entrada, mesmo texto): campos em ordem de nome, classes na ordem em que são usadas.
"""

import json
import keyword
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Objeto (caminho na AGI) → classe. Objetos com a mesma classe têm os campos somados.
NOMES_CLASSES = {
    "": "VendaAgi",
    "detalheItem[]": "ServicoAgi",
    "detalheItem[].apartamentos[]": "ApartamentoAgi",
    "detalheItem[].taxas[]": "TaxaServicoAgi",
    "trechos[]": "TrechoAgi",
    "trechos[].origem": "LocalTrechoAgi",
    "trechos[].destino": "LocalTrechoAgi",
    "recebimentos[]": "RecebimentoAgi",
    "pagamentos[]": "PagamentoAgi",
    "financeiroVinculado": "FinanceiroVinculadoAgi",
    "financeiroVinculado.contasPagar[]": "TituloVinculadoAgi",
    "financeiroVinculado.contasReceber[]": "TituloVinculadoAgi",
    "reembolsoVinculado[]": "ReembolsoVinculadoAgi",
    "sistemaExterno": "SistemaExternoAgi",
}

# Tipo do dicionário → anotação, na ordem em que entram numa união.
ESCALARES = (("bool", "bool"), ("int", "int"), ("float", "Decimal"), ("str", "str"))

# Nomes que não podem ser atributo do modelo sem `alias` (sombreariam o `BaseModel`).
RESERVADOS = frozenset(dir(BaseModel))


def _nome_classe(objeto: str) -> str:
    if objeto in NOMES_CLASSES:
        return NOMES_CLASSES[objeto]
    ultimo = objeto.rpartition(".")[2].replace("[]", "")
    partes = [p for p in re.split(r"[\W_]+", ultimo) if p]
    nome = "".join(p[:1].upper() + p[1:] for p in partes)
    if not nome or nome[0].isdigit():
        nome = "Objeto" + nome
    return nome + "Agi"


def _nome_python(nome: str, usados: set[str]) -> str:
    """Identificador válido para o campo; quando difere do nome da AGI, o campo leva `alias`."""
    candidato = re.sub(r"\W", "_", nome)
    if not candidato or candidato[0].isdigit() or candidato.startswith("_"):
        candidato = "campo_" + candidato.lstrip("_")
    if candidato.startswith("model_"):
        candidato = "campo_" + candidato
    if keyword.iskeyword(candidato) or candidato in RESERVADOS:
        candidato += "_"
    while candidato in usados:
        candidato += "_"
    usados.add(candidato)
    return candidato


def _juntar(listas: list[list[str]]) -> list[str]:
    """União em ordem, sem repetir; `int` com `Decimal` vira só `Decimal`."""
    membros: list[str] = []
    for lista in listas:
        membros.extend(m for m in lista if m not in membros)
    if "Decimal" in membros and "int" in membros:
        membros.remove("int")
    return membros


class _Gerador:
    def __init__(self, campos: dict[str, dict[str, Any]]) -> None:
        self.tipos = {caminho: set(info.get("tipos", {})) for caminho, info in campos.items()}
        # objeto → nome do campo → caminhos (mais de um quando objetos dividem a classe)
        self.filhos: dict[str, dict[str, list[str]]] = {"": {}}
        for caminho in sorted(campos):
            if caminho.endswith("[]"):
                continue  # descreve os itens da lista; não é campo
            pai, _, nome = caminho.rpartition(".")
            self.filhos.setdefault(pai, {}).setdefault(nome, []).append(caminho)
        objetos = set(self.filhos) | {c for c, tipos in self.tipos.items() if "object" in tipos}
        self.classe_de = {objeto: _nome_classe(objeto) for objeto in objetos}
        self.objetos_da_classe: dict[str, list[str]] = {}
        for objeto in sorted(objetos):
            self.objetos_da_classe.setdefault(self.classe_de[objeto], []).append(objeto)
        self.usa: set[str] = set()  # "Any", "Decimal", "Field": o que importar

    def _membros(self, caminho: str, usadas: list[str]) -> list[str]:
        """Tipos possíveis do valor no caminho, sem `None`."""
        tipos = self.tipos.get(caminho, set())
        membros: list[str] = []
        if "array" in tipos:
            membros.append(f"list[{self._item(caminho + '[]', usadas)}]")
        if caminho in self.classe_de:
            membros.append(self.classe_de[caminho])
            usadas.append(self.classe_de[caminho])
        membros.extend(anotacao for tipo, anotacao in ESCALARES if tipo in tipos)
        if "Decimal" in membros:
            self.usa.add("Decimal")
        return membros

    def _item(self, caminho: str, usadas: list[str]) -> str:
        membros = _juntar([self._membros(caminho, usadas)])
        if not membros:
            self.usa.add("Any")
            return "Any"  # lista sem item conhecido
        texto = " | ".join(membros)
        return texto + " | None" if "null" in self.tipos.get(caminho, set()) else texto

    def _classe(self, classe: str, usadas: list[str]) -> list[str]:
        objetos = self.objetos_da_classe[classe]
        campos: dict[str, list[str]] = {}
        for objeto in objetos:
            for nome, caminhos in self.filhos.get(objeto, {}).items():
                campos.setdefault(nome, []).extend(caminhos)
        if objetos == [""]:
            descricao = "Venda da AGI: cada item da lista `vendas` da resposta."
        else:
            onde = [f"`{objeto}`" for objeto in objetos]
            lista = onde[0] if len(onde) == 1 else ", ".join(onde[:-1]) + " e " + onde[-1]
            descricao = f"Objeto da AGI em {lista}."
        linhas = [
            f"class {classe}(BaseModel):",
            f'    """{descricao}"""',
            "",
            '    model_config = ConfigDict(extra="allow")',
        ]
        if campos:
            linhas.append("")
        usados: set[str] = set()
        for nome in sorted(campos):
            membros = _juntar([self._membros(caminho, usadas) for caminho in campos[nome]])
            if membros:
                anotacao = " | ".join(membros) + " | None"
            else:
                anotacao = "Any"  # só visto vazio (null): qualquer valor serve
                self.usa.add("Any")
            atributo = _nome_python(nome, usados)
            if atributo == nome:
                linhas.append(f"    {atributo}: {anotacao} = None")
            else:
                self.usa.add("Field")
                linhas.append(f"    {atributo}: {anotacao} = Field(default=None, alias={nome!r})")
        return linhas

    def _folhas(self) -> list[str]:
        """Caminhos sem campo de objeto abaixo deles: escalares e listas sem item objeto."""
        return sorted(
            caminho
            for caminho in self.tipos
            if not caminho.endswith("[]")
            and not any(o.startswith((caminho + ".", caminho + "[].")) for o in self.tipos)
        )

    def gerar(self) -> str:
        blocos: list[str] = []
        emitidas: set[str] = set()

        def emitir(classe: str) -> None:
            if classe in emitidas:
                return
            emitidas.add(classe)
            usadas: list[str] = []
            linhas = self._classe(classe, usadas)
            for dependencia in usadas:
                emitir(dependencia)  # antes de quem usa: anotações sem referência adiante
            blocos.append("\n".join(linhas))

        emitir(NOMES_CLASSES[""])
        caminhos = [f"        {caminho!r}," for caminho in self._folhas()]
        rodape = [
            "# Caminhos de folha conhecidos (`[]` no lugar dos índices); o resto é desconhecido.",
            "CAMINHOS_CONHECIDOS: frozenset[str] = frozenset(",
            "    {",
            *caminhos,
            "    }",
            ")",
        ]
        return "\n\n\n".join([self._cabecalho(), *blocos, "\n".join(rodape)]) + "\n"

    def _cabecalho(self) -> str:
        linhas = [
            '"""Modelo da venda da AGI. GERADO por scripts/gerar_modelos.py: não editar à mão.',
            "",
            "Só nomes e tipos do dicionário de campos. Todo campo é opcional; campo novo é aceito.",
            '"""',
            "",
        ]
        if "Decimal" in self.usa:
            linhas.append("from decimal import Decimal")
        if "Any" in self.usa:
            linhas.append("from typing import Any")
        if "Decimal" in self.usa or "Any" in self.usa:
            linhas.append("")
        pydantic = (
            "BaseModel, ConfigDict, Field" if "Field" in self.usa else "BaseModel, ConfigDict"
        )
        linhas.append(f"from pydantic import {pydantic}")
        return "\n".join(linhas)


def gerar(campos: dict[str, dict[str, Any]]) -> str:
    """Código Python do modelo para os caminhos do dicionário (`detalheItem[].taxas[].x`…)."""
    gerador = _Gerador(campos)
    return gerador.gerar()


def main(argumentos: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    if len(argumentos) != 1:
        print("uso: gerar_modelos.py <dicionario_campos.json>", file=sys.stderr)
        return 2
    dicionario = json.loads(Path(argumentos[0]).read_text(encoding="utf-8"))
    sys.stdout.write(gerar(dicionario["campos"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
