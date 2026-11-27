import asyncio
import base64
import gc
import json
import logging
from datetime import date
from decimal import Decimal
from types import ModuleType
from typing import Any

import httpx
import pytest

from stur_api.agi.cliente import ClienteAgi, FiltroAgi, janela_larga
from stur_api.config import Configuracao
from stur_api.erros import (
    ApiSturAcessoRecusado,
    ApiSturRespostaInvalida,
    ApiSturSemResposta,
    ErroAplicacao,
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


# --- intervalo entre logins e espera depois de recusa ---


def _login_certo(relogio: RelogioFixo) -> httpx.Response:
    return httpx.Response(200, json={"token": jwt_falso(relogio.agora().timestamp() + 3600)})


def _responder_login_com(agi: AgiFalsa, resposta: httpx.Response) -> None:
    agi.login.side_effect = None
    agi.login.return_value = resposta


async def test_verificacoes_dentro_do_intervalo_fazem_um_login(
    cliente: ClienteAgi, agi: AgiFalsa
) -> None:
    await asyncio.gather(*(cliente.verificar_acesso() for _ in range(20)))
    for _ in range(5):
        await cliente.verificar_acesso()
    assert agi.login.call_count == 1


async def test_verificacao_faz_novo_login_depois_do_intervalo(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    await cliente.verificar_acesso()
    relogio.avancar(60)
    await cliente.verificar_acesso()
    assert agi.login.call_count == 2


async def test_recusa_vale_para_todos_dentro_do_intervalo(
    cliente: ClienteAgi, agi: AgiFalsa
) -> None:
    _responder_login_com(agi, httpx.Response(401))
    resultados = await asyncio.gather(
        *(cliente.buscar_vendas(FILTRO_NUMERO) for _ in range(10)),
        *(cliente.verificar_acesso() for _ in range(10)),
        return_exceptions=True,
    )
    recusas = [r for r in resultados if isinstance(r, ApiSturAcessoRecusado)]
    assert len(recusas) == 20
    assert all(r.detalhe == {"status": 401} for r in recusas)
    assert agi.login.call_count == 1
    assert agi.reservas.call_count == 0


async def test_depois_do_intervalo_tenta_de_novo_e_volta_a_funcionar(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    _responder_login_com(agi, httpx.Response(401))
    with pytest.raises(ApiSturAcessoRecusado):
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 1
    relogio.avancar(59)
    with pytest.raises(ApiSturAcessoRecusado):
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert agi.login.call_count == 1
    _responder_login_com(agi, _login_certo(relogio))
    relogio.avancar(1)
    vendas = await cliente.buscar_vendas(FILTRO_NUMERO)
    assert [v["reserva"] for v in vendas] == [90000001]
    assert agi.login.call_count == 2


async def test_falha_sem_resposta_nao_segura_a_proxima_busca(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    agi.login.side_effect = [httpx.Response(500), _login_certo(relogio)]
    with pytest.raises(ApiSturSemResposta):
        await cliente.buscar_vendas(FILTRO_NUMERO)
    vendas = await cliente.buscar_vendas(FILTRO_NUMERO)
    assert [v["reserva"] for v in vendas] == [90000001]
    assert agi.login.call_count == 2


async def test_verificacao_repete_a_falha_recente_sem_novo_login(
    cliente: ClienteAgi, agi: AgiFalsa
) -> None:
    _responder_login_com(agi, httpx.Response(500))
    for _ in range(2):
        with pytest.raises(ApiSturSemResposta):
            await cliente.verificar_acesso()
    assert agi.login.call_count == 1


async def test_intervalo_zero_desliga_a_espera(
    cliente: ClienteAgi, agi: AgiFalsa, config: Configuracao
) -> None:
    config.agi_intervalo_login_s = 0
    await cliente.verificar_acesso()
    await cliente.verificar_acesso()
    assert agi.login.call_count == 2


# O cliente guarda o resultado do último login, nunca a exceção: o traceback dela leva ao
# quadro com a senha, e o contexto, ao pedido do httpx com o JSON do login.

# colaboradores recebidos de fora e a trava: não são estado do que o cliente guardou
_FORA_DO_ESTADO = ("_config", "_http", "_relogio", "_trava_login")


def _excecoes_guardadas(cliente: ClienteAgi) -> list[BaseException]:
    """As exceções alcançáveis a partir do estado guardado no cliente."""
    pendentes = [v for nome, v in vars(cliente).items() if nome not in _FORA_DO_ESTADO]
    vistos: set[int] = set()
    achadas: list[BaseException] = []
    while pendentes:
        objeto = pendentes.pop()
        if id(objeto) in vistos or isinstance(objeto, type | ModuleType):
            continue
        vistos.add(id(objeto))
        if isinstance(objeto, BaseException):
            achadas.append(objeto)
        pendentes.extend(gc.get_referents(objeto))
    return achadas


async def test_falha_no_login_nao_deixa_excecao_guardada_no_cliente(
    cliente: ClienteAgi, agi: AgiFalsa
) -> None:
    agi.login.side_effect = httpx.ConnectError("sem rede")
    with pytest.raises(ApiSturSemResposta):
        await cliente.buscar_vendas(FILTRO_NUMERO)
    assert _excecoes_guardadas(cliente) == []
    with pytest.raises(ApiSturSemResposta):
        await cliente.verificar_acesso()  # repete a falha guardada
    assert _excecoes_guardadas(cliente) == []


@pytest.mark.parametrize(
    "falha",
    [httpx.Response(500), httpx.ConnectError("sem rede"), httpx.Response(401)],
    ids=["500", "transporte", "recusa"],
)
async def test_cada_verificacao_levanta_um_erro_novo_e_igual(
    cliente: ClienteAgi, agi: AgiFalsa, falha: httpx.Response | httpx.ConnectError
) -> None:
    agi.login.side_effect = [falha]
    erros: list[ErroAplicacao] = []
    for _ in range(3):  # a tentativa e duas repetições dentro do intervalo
        with pytest.raises(ErroAplicacao) as erro:
            await cliente.verificar_acesso()
        erros.append(erro.value)
    assert agi.login.call_count == 1
    assert len({id(e) for e in erros}) == 3
    original = erros[0]
    for repetido in erros[1:]:
        assert type(repetido) is type(original)
        assert (repetido.status_http, repetido.codigo, repetido.mensagem, repetido.detalhe) == (
            original.status_http,
            original.codigo,
            original.mensagem,
            original.detalhe,
        )
        assert str(repetido) == str(original)
        assert repetido.__context__ is None
        assert repetido.__cause__ is None


async def test_recusa_na_verificacao_nao_derruba_o_token_em_uso(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    await cliente.buscar_vendas(FILTRO_NUMERO)
    token_antigo = agi.reservas.calls.last.request.headers["Authorization"]
    _responder_login_com(agi, httpx.Response(401))
    relogio.avancar(60)
    with pytest.raises(ApiSturAcessoRecusado):
        await cliente.verificar_acesso()
    assert agi.login.call_count == 2
    vendas = await cliente.buscar_vendas(FILTRO_NUMERO)
    assert [v["reserva"] for v in vendas] == [90000001]
    assert agi.reservas.calls.last.request.headers["Authorization"] == token_antigo
    assert agi.login.call_count == 2


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


# --- quem desiste no meio do login não fura a espera entre logins ---


class _LoginPreso:
    """Login que só responde quando `soltar` for ligado."""

    def __init__(self, resposta: httpx.Response) -> None:
        self.resposta = resposta
        self.comecou = asyncio.Event()
        self.soltar = asyncio.Event()
        # contado aqui: o `call_count` do respx não vê a chamada cortada no meio
        self.enviados = 0

    async def responder(self, _pedido: httpx.Request) -> httpx.Response:
        self.enviados += 1
        self.comecou.set()
        await self.soltar.wait()
        return self.resposta


async def _desistir_no_meio_do_login(preso: _LoginPreso, tarefa: asyncio.Task[Any]) -> None:
    async with asyncio.timeout(1):
        await preso.comecou.wait()
    tarefa.cancel()
    await asyncio.sleep(0.02)
    preso.soltar.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(tarefa, 1)


async def test_login_de_quem_desistiu_termina_e_o_token_serve_ao_proximo(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    preso = _LoginPreso(_login_certo(relogio))
    agi.login.side_effect = preso.responder
    quem_desiste = asyncio.create_task(cliente.buscar_vendas(FILTRO_NUMERO))
    await _desistir_no_meio_do_login(preso, quem_desiste)

    vendas = await asyncio.wait_for(cliente.buscar_vendas(FILTRO_NUMERO), 1)

    assert [v["reserva"] for v in vendas] == [90000001]
    assert preso.enviados == 1


async def test_recusa_do_login_de_quem_desistiu_segura_o_proximo(
    cliente: ClienteAgi, agi: AgiFalsa
) -> None:
    preso = _LoginPreso(httpx.Response(401))
    agi.login.side_effect = preso.responder
    quem_desiste = asyncio.create_task(cliente.verificar_acesso())
    await _desistir_no_meio_do_login(preso, quem_desiste)

    with pytest.raises(ApiSturAcessoRecusado):
        await asyncio.wait_for(cliente.buscar_vendas(FILTRO_NUMERO), 1)

    assert preso.enviados == 1


async def test_quem_chega_durante_o_login_abandonado_nao_faz_outro(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    preso = _LoginPreso(_login_certo(relogio))
    agi.login.side_effect = preso.responder
    quem_desiste = asyncio.create_task(cliente.buscar_vendas(FILTRO_NUMERO))
    async with asyncio.timeout(1):
        await preso.comecou.wait()
    quem_fica = asyncio.create_task(cliente.buscar_vendas(FILTRO_NUMERO))
    quem_desiste.cancel()
    await asyncio.sleep(0.02)
    preso.soltar.set()

    vendas = await asyncio.wait_for(quem_fica, 1)

    assert [v["reserva"] for v in vendas] == [90000001]
    assert preso.enviados == 1
