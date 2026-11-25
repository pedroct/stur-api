"""Texto da AGI comparado sem depender de acento, caixa ou espaço repetido (PRD 8.4)."""

import unicodedata


def normalizar(texto: str) -> str:
    """Sem acento, em maiúsculas e com os espaços colapsados: `" Locação "` vira `"LOCACAO"`."""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_marcas = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_marcas.upper().split())


def contem(texto: str | None, busca: str) -> bool:
    """`busca` aparece em `texto`, sem depender de acento nem de caixa. Texto ausente não contém."""
    if texto is None:
        return False
    return normalizar(busca) in normalizar(texto)
