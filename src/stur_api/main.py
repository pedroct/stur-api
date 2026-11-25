from fastapi import FastAPI

from stur_api.rotas import saude


def criar_app() -> FastAPI:
    app = FastAPI(title="stur-api", version="0.1.0")
    app.include_router(saude.roteador, prefix="/api/v1")
    return app


app = criar_app()
