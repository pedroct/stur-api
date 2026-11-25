import asyncio
import base64
import json
import logging
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from stur_api.agi.cliente import ClienteAgi, FiltroAgi, janela_larga
from stur_api.config import Configuracao
from stur_api.erros import (
    ApiSturAcessoRecusado,
    ApiSturRespostaInvalida,
    ApiSturSemResposta,
)
from tests import fabrica
from tests.agi_falsa import AgiFalsa, jwt_falso
from tests.conftest import RelogioFixo

FILTRO_NUMERO = FiltroAgi("EMISSAO", date(2020, 1, 1), date(2027, 12, 31), reserva=90000001)


def _leves(quantidade: int) -> list[dict[str, Any]]:
    """Vendas mínimas (só `reserva`) para testar paginação sem montar 2000 vendas completas."""
    return [{"reserva": 90000001 + i} for i in range(quantidade)]


async def test_reaproveita_o_token(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    await cliente.buscar_vendas(FILTRO_NUMERO)
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 1


async def test_renova_o_token_antes_de_vencer(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    await cliente.buscar_vendas(FILTRO_NUMERO)
    relogio.avancar(3600 - 30)
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 2


async def test_nao_renova_com_folga_maior_que_60_segundos(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    await cliente.buscar_vendas(FILTRO_NUMERO)
    relogio.avancar(3600 - 120)
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 1


async def test_dois_pedidos_simultaneos_fazem_um_login(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    await asyncio.gather(cliente.buscar_vendas(FILTRO_NUMERO), cliente.buscar_vendas(FILTRO_NUMERO))
    assert agi.login.call_count == 1


async def test_401_refaz_login_e_repete_uma_vez(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.reservas.side_effect = [
        httpx.Response(401),
        httpx.Response(200, text=fabrica.resposta_agi([fabrica.venda()])),
    ]
    assert len(await cliente.buscar_vendas(FILTRO_NUMERO)) == 1
    assert agi.login.call_count == 2


async def test_dois_401_e_acesso_recusado(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.reservas.side_effect = [httpx.Response(401), httpx.Response(401)]
    with pytest.raises(ApiSturAcessoRecusado):
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 2


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_login_recusado_e_acesso_recusado(
    cliente: ClienteAgi, agi: AgiFalsa, status: int
) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(status)
    with pytest.raises(ApiSturAcessoRecusado):
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.reservas.call_count == 0


async def test_tempo_esgotado_e_sem_resposta(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.reservas.side_effect = httpx.ReadTimeout("demorou")
    with pytest.raises(ApiSturSemResposta) as erro:
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert "30 segundos" in erro.value.mensagem


async def test_falha_de_conexao_no_login_e_sem_resposta(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.login.side_effect = httpx.ConnectError("sem rede")
    with pytest.raises(ApiSturSemResposta):
        await cliente.buscar_vendas(FILTRO_NUMERO)


@pytest.mark.parametrize("erro_httpx", [httpx.DecodingError, httpx.TooManyRedirects])
async def test_erro_do_httpx_nao_traduzido_e_resposta_invalida(
    cliente: ClienteAgi, agi: AgiFalsa, erro_httpx: type[httpx.HTTPError]
) -> None:
    agi.reservas.side_effect = erro_httpx("x")
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert erro.value.detalhe == {"erro": erro_httpx.__name__}
    assert erro.value.__cause__ is None
    assert erro.value.__suppress_context__


async def test_erro_do_httpx_nao_traduzido_no_login_e_resposta_invalida(
    cliente: ClienteAgi, agi: AgiFalsa
) -> None:
    agi.login.side_effect = httpx.DecodingError("x")
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        await cliente.verificar_acesso()
    assert erro.value.detalhe == {"erro": "DecodingError"}


async def test_500_e_sem_resposta(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.reservas.return_value = httpx.Response(500)
    with pytest.raises(ApiSturSemResposta):
        await cliente.buscar_vendas(FILTRO_NUMERO)


async def test_400_traz_o_erro_da_agi(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.reservas.return_value = httpx.Response(
        400, json={"Sucesso": False, "Erro": "ItensPorPagina inválido", "Detalhes": "x"}
    )
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert erro.value.detalhe == {"erro": "ItensPorPagina inválido", "detalhes": "x"}


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, text="isto não é JSON"),
        httpx.Response(200, json={"pagina": 1, "registrosnapagina": 0}),
        httpx.Response(200, json={"vendas": "não é lista"}),
        httpx.Response(200, json=[]),
    ],
)
async def test_200_sem_a_lista_e_resposta_invalida(
    cliente: ClienteAgi, agi: AgiFalsa, resposta: httpx.Response
) -> None:
    agi.reservas.return_value = resposta
    with pytest.raises(ApiSturRespostaInvalida):
        await cliente.buscar_vendas(FILTRO_NUMERO)


async def test_aceita_a_lista_com_inicial_maiuscula(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.reservas.return_value = httpx.Response(200, json={"Vendas": [{"reserva": 90000001}]})
    assert await cliente.buscar_vendas(FILTRO_NUMERO) == [{"reserva": 90000001}]


async def test_segue_as_paginas_cheias(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.vendas = _leves(2005)
    filtro = FiltroAgi("EMISSAO", date(2020, 1, 1), date(2027, 12, 31), itens_por_pagina=2000)
    vendas = await cliente.buscar_vendas(filtro)
    assert len(vendas) == 2005
    assert agi.reservas.call_count == 2
    assert [_corpo(c.request)["Pagina"] for c in agi.reservas.calls] == [1, 2]


async def test_pagina_exatamente_cheia_pede_mais_uma(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.vendas = _leves(100)
    filtro = FiltroAgi("EMISSAO", date(2020, 1, 1), date(2027, 12, 31), itens_por_pagina=100)
    assert len(await cliente.buscar_vendas(filtro)) == 100
    assert agi.reservas.call_count == 2  # a página 2 veio vazia


async def test_so_primeira_pagina_para_na_primeira(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.vendas = _leves(250)
    filtro = FiltroAgi(
        "EMISSAO",
        date(2020, 1, 1),
        date(2027, 12, 31),
        itens_por_pagina=100,
        so_primeira_pagina=True,
    )
    assert len(await cliente.buscar_vendas(filtro)) == 100
    assert agi.reservas.call_count == 1


async def test_para_em_50_paginas_com_resposta_invalida(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.vendas = _leves(100 * 51)
    filtro = FiltroAgi("EMISSAO", date(2020, 1, 1), date(2027, 12, 31), itens_por_pagina=100)
    with pytest.raises(ApiSturRespostaInvalida):
        await cliente.buscar_vendas(filtro)
    assert agi.reservas.call_count == 50


async def test_corpo_so_leva_os_filtros_presentes(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    await cliente.buscar_vendas(FILTRO_NUMERO)
    corpo = _corpo(agi.reservas.calls.last.request)
    assert corpo == {
        "Pagina": 1,
        "ItensPorPagina": 100,
        "TipoData": "EMISSAO",
        "DataInicial": "2020-01-01",
        "DataFinal": "2027-12-31",
        "Reserva": 90000001,
    }


async def test_corpo_leva_id_e_status_quando_pedidos(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    filtro = FiltroAgi(
        "ALTERACAO", date(2026, 11, 1), date(2026, 11, 30), id=1001, status="FECHADA"
    )
    await cliente.buscar_vendas(filtro)
    corpo = _corpo(agi.reservas.calls.last.request)
    assert corpo["TipoData"] == "ALTERACAO"
    assert corpo["Id"] == 1001
    assert corpo["Status"] == "FECHADA"
    assert "Reserva" not in corpo


async def test_manda_o_token_no_cabecalho(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    await cliente.buscar_vendas(FILTRO_NUMERO)
    login = _corpo(agi.login.calls.last.request)
    assert login == {"Username": "usuario-de-teste", "Password": "senha-de-teste"}
    assert agi.reservas.calls.last.request.headers["Authorization"].startswith("Bearer ")


@pytest.mark.parametrize("chave", ["token", "accessToken", "ACCESS_TOKEN", "Jwt", "bearer"])
async def test_aceita_as_variantes_da_chave_do_token(
    cliente: ClienteAgi, agi: AgiFalsa, chave: str
) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(200, json={chave: "abc.def.ghi"})
    await cliente.buscar_vendas(FILTRO_NUMERO)
    cabecalho = agi.reservas.calls.last.request.headers["Authorization"]
    assert cabecalho == "Bearer abc.def.ghi"


async def test_aceita_o_jwt_puro_no_corpo(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(200, text="abc.def.ghi")
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.reservas.calls.last.request.headers["Authorization"] == "Bearer abc.def.ghi"


async def test_login_sem_token_e_resposta_invalida(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(200, json={"ok": True})
    with pytest.raises(ApiSturRespostaInvalida):
        await cliente.buscar_vendas(FILTRO_NUMERO)


async def test_token_sem_exp_vale_55_minutos(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(200, json={"token": "sem-exp"})
    await cliente.buscar_vendas(FILTRO_NUMERO)
    relogio.avancar(55 * 60 - 120)
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 1
    relogio.avancar(90)  # faltam 30 s
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 2


@pytest.mark.parametrize("exp", [1e30, -1e30])
async def test_exp_fora_do_alcance_do_datetime_cai_na_regra_de_55_minutos(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo, exp: float
) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(200, json={"token": jwt_falso(exp)})
    await cliente.buscar_vendas(FILTRO_NUMERO)
    relogio.avancar(55 * 60 - 120)
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 1
    relogio.avancar(90)  # faltam 30 s
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 2


async def test_valores_chegam_como_decimal(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    vendas = await cliente.buscar_vendas(FILTRO_NUMERO)
    total = vendas[0]["totalCliente"]
    assert isinstance(total, Decimal)
    assert total == Decimal("1050.01")


async def test_verificar_acesso_faz_login(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    await cliente.verificar_acesso()
    assert agi.login.call_count == 1
    assert agi.reservas.call_count == 0


async def test_verificar_acesso_recusado(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(401)
    with pytest.raises(ApiSturAcessoRecusado):
        await cliente.verificar_acesso()


async def test_log_nao_tem_corpo(
    cliente: ClienteAgi, agi: AgiFalsa, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert "CLIENTE EXEMPLO" not in caplog.text
    assert "90000001" in caplog.text


async def test_log_proprio_nao_tem_url_nem_credenciais_nem_token(
    cliente: ClienteAgi, agi: AgiFalsa, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    await cliente.buscar_vendas(FILTRO_NUMERO)
    proprio = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("agi"))
    assert "agi.reservas" in {r.name for r in caplog.records}
    for proibido in ("exemplo.invalid", "usuario-de-teste", "senha-de-teste", "Bearer", "eyJ"):
        assert proibido not in proprio


def _corpo(pedido: httpx.Request) -> dict[str, Any]:
    corpo: dict[str, Any] = json.loads(pedido.content)
    return corpo


def test_janela_larga_vai_do_inicio_configurado_ao_fim_do_ano_seguinte(
    config: Configuracao,
) -> None:
    assert janela_larga(config, date(2026, 11, 25)) == (date(2020, 1, 1), date(2027, 12, 31))


# --- casos de borda do login e das respostas de erro ---


def _jwt_com_exp(exp: object) -> str:
    """JWT cujo `exp` não é número (o cliente deve ignorá-lo)."""

    def parte(dados: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(dados).encode()).rstrip(b"=").decode()

    return f"{parte({'alg': 'none'})}.{parte({'exp': exp})}.assinatura"


async def test_aceita_o_token_como_string_json(cliente: ClienteAgi, agi: AgiFalsa) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(200, text='"abc.def.ghi"')
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.reservas.calls.last.request.headers["Authorization"] == "Bearer abc.def.ghi"


@pytest.mark.parametrize("corpo", ['["abc.def.ghi"]', "12345", '""'])
async def test_login_com_json_que_nao_traz_token_e_resposta_invalida(
    cliente: ClienteAgi, agi: AgiFalsa, corpo: str
) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(200, text=corpo)
    with pytest.raises(ApiSturRespostaInvalida):
        await cliente.buscar_vendas(FILTRO_NUMERO)


@pytest.mark.parametrize("exp", ["amanhã", True, None, [1]])
async def test_exp_que_nao_e_numero_cai_na_regra_de_55_minutos(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo, exp: object
) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(200, json={"token": _jwt_com_exp(exp)})
    await cliente.buscar_vendas(FILTRO_NUMERO)
    relogio.avancar(55 * 60 - 120)
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 1
    relogio.avancar(90)  # faltam 30 s
    await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 2


@pytest.mark.parametrize("status", [302, 404, 409])
async def test_outro_status_na_busca_e_resposta_invalida(
    cliente: ClienteAgi, agi: AgiFalsa, status: int
) -> None:
    agi.reservas.return_value = httpx.Response(status)
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert erro.value.detalhe == {"status": status}


async def test_outro_status_no_login_e_resposta_invalida(
    cliente: ClienteAgi, agi: AgiFalsa
) -> None:
    agi.login.side_effect = None
    agi.login.return_value = httpx.Response(404)
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert erro.value.detalhe == {"status": 404}


@pytest.mark.parametrize(
    "resposta",
    [httpx.Response(400, text="isto não é JSON"), httpx.Response(400, json=["Erro"])],
)
async def test_400_sem_objeto_json_nao_traz_o_corpo(
    cliente: ClienteAgi, agi: AgiFalsa, resposta: httpx.Response
) -> None:
    agi.reservas.return_value = resposta
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert erro.value.detalhe == {"erro": None, "detalhes": None}
