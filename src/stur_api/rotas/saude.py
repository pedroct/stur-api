from fastapi import APIRouter

roteador = APIRouter()


@roteador.get("/saude")
def saude() -> dict[str, str]:
    return {"aplicacao": "ok"}
