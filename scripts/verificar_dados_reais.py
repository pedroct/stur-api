"""Gancho do pre-commit: recusa dados reais em arquivos versionados (repositório público)."""

import re
import sys
from pathlib import Path

# O padrão do identificador da A3 é montado por concatenação para o script não casar consigo mesmo.
PADROES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b15[5-6]\d{5}\b"), "número de reserva real"),
    (re.compile("(?i)" + "a3" + "turismo"), "identificador da A3"),
]


def verificar(arquivos: list[Path]) -> list[str]:
    """Devolve uma mensagem `arquivo:linha: motivo` para cada ocorrência de dado real."""
    problemas: list[str] = []
    for arquivo in arquivos:
        try:
            linhas = arquivo.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
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
