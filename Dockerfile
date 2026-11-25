# syntax=docker/dockerfile:1
# Imagem base fixada por digest (índice multi-arquitetura de python:3.12-slim-bookworm,
# consultado com `docker buildx imagetools inspect`); a tag fica ao lado para leitura.
ARG PYTHON_IMAGEM=python:3.12-slim-bookworm@sha256:44cf1793efa7c7a476bb0f2cff81443f4a072c90c1cb127e2924933daa3e8c64

# ── Stage: uv (binário fixado por versão e digest) ─────────────────────────────
FROM ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 AS uv

# ── Stage: builder ─────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGEM} AS builder
WORKDIR /app
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# Cache de camada: lock e manifesto mudam menos que o código
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen

# ── Stage: runtime ─────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGEM} AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# Mesmo caminho do install editable do builder
COPY --from=builder /app/src ./src
ENV PATH="/app/.venv/bin:$PATH" \
    TZ="America/Fortaleza" \
    LANG="C.UTF-8" \
    PYTHONUNBUFFERED=1
# Non-root com UID/GID explícito
RUN addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app
USER appuser
EXPOSE 8000
# Sem curl na imagem: o healthcheck usa urllib. A rota não depende da AGI.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/saude', timeout=4)" || exit 1
# --no-access-log: o access log do uvicorn grava a query (texto dos filtros).
CMD ["uvicorn", "stur_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
