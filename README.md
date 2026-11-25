# stur-api

API de consulta de reserva da A3 Turismo: lê a AGI do Stur e devolve a venda
já calculada e verificada. Somente leitura.

Este repositório é público: não coloque dados reais em código, testes ou
documentos. Números de teste: reserva `90000001` em diante, idreserva `1001`
em diante.

## Desenvolvimento

```bash
uv sync
cp .env.example .env          # preencha só no seu ambiente
uv run pre-commit install
TZ=UTC uv run pytest -q
uv run ruff check . && uv run mypy src
uv run uvicorn stur_api.main:app --no-access-log
```

O access log do uvicorn fica desligado de propósito: ele grava a query.

## Rotas

- `GET /api/v1/saude` devolve `{"aplicacao": "ok"}`.
