"""Gancho do pre-commit e passo do CI: recusa dados reais em arquivos versionados (repo público).

Falha fechada: o caminho de todo arquivo é verificado; o conteúdo é lido em bytes e decodificado
com `errors="replace"` (latin-1/cp1252 não escapam); erro de leitura vira problema. Só o conteúdo
de arquivo com byte NUL (binário) não é varrido, para não gerar falso positivo; o caminho dele é.
"""

import re
import sys
from pathlib import Path

# O padrão do identificador da A3 é montado por concatenação para o script não casar consigo mesmo.
# O número de reserva só casa quando não faz parte de um número maior (`(?<!\d)`/`(?!\d)`):
# `\b` não separava dígito de `_`/letra e deixava passar `RE_<n>`, `<n>_tela`, `v<n>.png`.
PADROES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<!\d)15[5-6]\d{5}(?!\d)"), "número de reserva real"),
    (re.compile("(?i)" + "a3" + "turismo"), "identificador da A3"),
]


def verificar(arquivos: list[Path]) -> list[str]:
    """Devolve uma mensagem por ocorrência de dado real: `arquivo:linha: motivo` no conteúdo,
    `arquivo: motivo (no caminho)` no caminho, `arquivo: arquivo não pôde ser lido (Erro)`."""
    problemas: list[str] = []
    for arquivo in arquivos:
        for padrao, motivo in PADROES:
            if padrao.search(str(arquivo)):
                problemas.append(f"{arquivo}: {motivo} (no caminho)")
        try:
            conteudo = arquivo.read_bytes()
        except OSError as erro:
            problemas.append(f"{arquivo}: arquivo não pôde ser lido ({type(erro).__name__})")
            continue
        if b"\x00" in conteudo:
            continue
        linhas = conteudo.decode("utf-8", errors="replace").splitlines()
        for numero, linha in enumerate(linhas, start=1):
            for padrao, motivo in PADROES:
                if padrao.search(linha):
                    problemas.append(f"{arquivo}:{numero}: {motivo}")
    return problemas


def main(argumentos: list[str] | None = None) -> int:
    arquivos = [Path(a) for a in (sys.argv[1:] if argumentos is None else argumentos)]
    problemas = verificar(arquivos)
    for problema in problemas:
        print(problema, file=sys.stderr)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
