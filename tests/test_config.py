from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from stur_api.config import Configuracao
from stur_api.relogio import RelogioSistema

OBRIGATORIAS = {
    "STUR_API_URL": "https://agi.exemplo.invalid",
    "STUR_API_USUARIO": "u",
    "STUR_API_SENHA": "s",
}


def _definir_obrigatorias(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in OBRIGATORIAS.items():
        monkeypatch.setenv(k, v)


def test_padroes_do_prd(monkeypatch: pytest.MonkeyPatch) -> None:
    _definir_obrigatorias(monkeypatch)
    c = Configuracao(_env_file=None)
    assert c.periodo_maximo_dias == 31
    assert c.linhas_por_pagina == 20
    assert c.opcoes_por_pagina == [20, 50, 100]
    assert c.tolerancia_real == Decimal("0.02")
    assert c.tolerancia_moeda_por_servico == Decimal("0.05")
    assert c.janela_inicio == date(2020, 1, 1)
    assert c.janela_fim(date(2026, 11, 25)) == date(2027, 12, 31)
    assert c.produtos_incentivo == ["INCENTIVO"]
    assert c.produtos_fee == ["TAXA FEE"]
    assert c.agi_tempo_limite_s == 30
    assert c.agi_itens_por_pagina == 2000
    assert c.cache_resultado_s == 300
    assert c.corte_trajeto_horas == 24


@pytest.mark.parametrize("valor", ["2001", "99"])
def test_itens_por_pagina_fora_da_faixa_da_agi_e_recusado(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    _definir_obrigatorias(monkeypatch)
    monkeypatch.setenv("AGI_ITENS_POR_PAGINA", valor)
    with pytest.raises(ValidationError):
        Configuracao(_env_file=None)


@pytest.mark.parametrize("valor", ["100", "2000"])
def test_itens_por_pagina_nos_limites_da_faixa_e_aceito(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    _definir_obrigatorias(monkeypatch)
    monkeypatch.setenv("AGI_ITENS_POR_PAGINA", valor)
    assert Configuracao(_env_file=None).agi_itens_por_pagina == int(valor)


def test_listas_e_decimais_vem_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    _definir_obrigatorias(monkeypatch)
    monkeypatch.setenv("OPCOES_POR_PAGINA", "[10, 25]")
    monkeypatch.setenv("PRODUTOS_FEE", '["TAXA FEE", "FEE EXTRA"]')
    monkeypatch.setenv("TOLERANCIA_REAL", "0.03")
    c = Configuracao(_env_file=None)
    assert c.opcoes_por_pagina == [10, 25]
    assert c.produtos_fee == ["TAXA FEE", "FEE EXTRA"]
    assert c.tolerancia_real == Decimal("0.03")


def test_acesso_a_agi_e_obrigatorio(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in OBRIGATORIAS:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ValidationError):
        Configuracao(_env_file=None)


def test_relogio_do_sistema_tem_fuso_de_fortaleza() -> None:
    assert RelogioSistema().agora().utcoffset() == timedelta(hours=-3)


def test_senha_nao_aparece_na_representacao(config: Configuracao) -> None:
    assert "senha-de-teste" not in repr(config)
    assert config.stur_api_senha.get_secret_value() == "senha-de-teste"
