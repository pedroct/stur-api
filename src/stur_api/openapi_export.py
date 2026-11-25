"""Exporta o contrato OpenAPI: `python -m stur_api.openapi_export > openapi.json`.

Saída determinística (chaves ordenadas, UTF-8, quebra de linha final): o CI compara com o
`openapi.json` versionado, e o plano 2 gera os tipos do frontend a partir dele.
"""

import json
import sys
from typing import Any

from stur_api.main import criar_app


def serializar(esquema: dict[str, Any]) -> str:
    return json.dumps(esquema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    # Bytes em UTF-8, qualquer que seja a codificação do terminal ou do pipe.
    sys.stdout.buffer.write(serializar(criar_app().openapi()).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
