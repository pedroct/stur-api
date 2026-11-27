from datetime import date
from decimal import Decimal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    """Parâmetros da aplicação, lidos do ambiente (e do `.env`). Padrões: PRD 9.2."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stur_api_url: str
    stur_api_usuario: str
    stur_api_senha: SecretStr

    janela_inicio: date = date(2020, 1, 1)
    periodo_maximo_dias: int = 31
    linhas_por_pagina: int = 20
    opcoes_por_pagina: list[int] = [20, 50, 100]

    agi_tempo_limite_s: int = 30
    agi_intervalo_login_s: int = Field(default=60, ge=0)
    agi_itens_por_pagina: int = Field(default=2000, ge=100, le=2000)
    cache_resultado_s: int = 300
    cache_resultado_max_linhas: int = Field(default=10_000, ge=0)
    consultas_simultaneas: int = Field(default=2, ge=1)

    tolerancia_real: Decimal = Decimal("0.02")
    tolerancia_moeda_por_servico: Decimal = Decimal("0.05")
    corte_trajeto_horas: int = 24

    produtos_fee: list[str] = ["TAXA FEE"]
    produtos_incentivo: list[str] = ["INCENTIVO"]

    def janela_fim(self, hoje: date) -> date:
        """Fim da janela larga: 31/12 do ano seguinte ao de `hoje` (PRD 8.2)."""
        return date(hoje.year + 1, 12, 31)
