import json

import httpx
import pytest

from stur_api.agi.campos import validar_venda
from stur_api.agi.cliente import ClienteAgi
from stur_api.agi.modelos import VendaAgi
from stur_api.erros import ApiSturRespostaInvalida
from stur_api.servicos.data_copia import DataDaCopia
from tests import fabrica
from tests.agi_falsa import AgiFalsa
from tests.conftest import RelogioFixo


def _vendas(*datas: str | None) -> list[VendaAgi]:
    return [
        validar_venda(fabrica.venda(idreserva=1001 + i, dtalteracaovinculado=data))
        for i, data in enumerate(datas)
    ]


async def test_registrar_devolve_a_maior_data_em_iso(
    cliente: ClienteAgi, relogio: RelogioFixo
) -> None:
    data_copia = DataDaCopia(cliente, relogio, 300)
    vendas = _vendas("2026-11-18 09:26:00", "2026-11-18T09:30:00", None, "1899-12-30 00:00:00")
    assert data_copia.registrar(vendas) == "2026-11-18T09:30:00"


async def test_registrar_sem_data_devolve_none(cliente: ClienteAgi, relogio: RelogioFixo) -> None:
    data_copia = DataDaCopia(cliente, relogio, 300)
    assert data_copia.registrar([]) is None
    assert data_copia.registrar(_vendas(None, "")) is None


async def test_registrar_data_em_formato_desconhecido_e_resposta_invalida(
    cliente: ClienteAgi, relogio: RelogioFixo
) -> None:
    data_copia = DataDaCopia(cliente, relogio, 300)
    with pytest.raises(ApiSturRespostaInvalida) as erro:
        data_copia.registrar(_vendas("18/11/2026 09:30"))
    assert erro.value.detalhe == ["dtalteracaovinculado: formato_de_data_invalido"]


async def test_obter_devolve_a_ultima_vista_sem_chamar_a_agi(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    data_copia = DataDaCopia(cliente, relogio, 300)
    data_copia.registrar(_vendas("2026-11-18 09:30:00"))
    assert await data_copia.obter() == "2026-11-18T09:30:00"
    assert agi.reservas.call_count == 0


async def test_obter_sem_nenhuma_vista_faz_a_consulta_pequena(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    agi.ultima_copia = "2026-11-18 09:28:00"
    data_copia = DataDaCopia(cliente, relogio, 300)
    assert await data_copia.obter() == "2026-11-18T09:28:00"
    corpo = json.loads(agi.reservas.calls.last.request.content)
    assert corpo == {
        "Pagina": 1,
        "ItensPorPagina": 100,
        "TipoData": "ALTERACAO",
        "DataInicial": "2020-01-01",
        "DataFinal": "2027-12-31",
    }
    assert await data_copia.obter() == "2026-11-18T09:28:00"
    assert agi.reservas.call_count == 1


async def test_obter_consulta_de_novo_quando_o_prazo_acaba(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    data_copia = DataDaCopia(cliente, relogio, 300)
    data_copia.registrar(_vendas("2026-11-18 09:30:00"))
    relogio.avancar(300)
    agi.ultima_copia = "2026-11-25 09:30:00"
    assert await data_copia.obter() == "2026-11-25T09:30:00"
    assert agi.reservas.call_count == 1


async def test_obter_com_falha_da_agi_devolve_none(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    agi.reservas.side_effect = httpx.ReadTimeout("x")
    assert await DataDaCopia(cliente, relogio, 300).obter() is None


async def test_obter_com_data_em_formato_desconhecido_devolve_none(
    cliente: ClienteAgi, agi: AgiFalsa, relogio: RelogioFixo
) -> None:
    agi.ultima_copia = "18/11/2026"
    assert await DataDaCopia(cliente, relogio, 300).obter() is None
