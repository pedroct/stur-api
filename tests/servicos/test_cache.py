from decimal import Decimal

from stur_api.contrato.calculos import ResumoIncentivos, ResumoResultado
from stur_api.contrato.consulta import ConsultaEcoada, ResultadoConsulta
from stur_api.dominio.consulta import ConsultaVendas
from stur_api.servicos.cache import CacheResultados
from tests.conftest import RelogioFixo

ZERO = Decimal("0")


def _resultado(relogio: RelogioFixo, reserva: int = 90000001) -> ResultadoConsulta:
    return ResultadoConsulta(
        consulta=ConsultaEcoada(
            reserva=reserva,
            tipo_data="emissao",
            de=None,
            ate=None,
            situacao=[],
            classificacao=[],
            fornecedor=None,
            cliente=None,
            emissor=None,
            janela_larga=True,
        ),
        consultado_em=relogio.agora(),
        dados_do_stur_ate=None,
        periodo_passa_da_copia=False,
        vendas=[],
        resumo=ResumoResultado(
            quantidade=0,
            total_cliente=ZERO,
            total_fornecedor=ZERO,
            margem=ZERO,
            percentual_lucro=None,
            nao_fecham=0,
            canceladas=0,
            incentivos=ResumoIncentivos(
                quantidade=0,
                valor=ZERO,
                margem_com_incentivos=ZERO,
                percentual_com_incentivos=None,
            ),
        ),
    )


def test_devolve_o_guardado_dentro_do_prazo(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio)
    consulta = ConsultaVendas(90000001)
    resultado = _resultado(relogio)
    cache.guardar(consulta, resultado)
    relogio.avancar(299)
    assert cache.obter(consulta) is resultado


def test_vence_quando_o_prazo_acaba(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio)
    consulta = ConsultaVendas(90000001)
    cache.guardar(consulta, _resultado(relogio))
    relogio.avancar(300)
    assert cache.obter(consulta) is None


def test_sem_nada_guardado_devolve_none(relogio: RelogioFixo) -> None:
    assert CacheResultados(300, relogio).obter(ConsultaVendas(90000001)) is None


def test_a_chave_e_a_consulta_inteira(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio)
    resultado = _resultado(relogio)
    cache.guardar(ConsultaVendas(90000001, situacoes=frozenset({"fechada"})), resultado)
    assert cache.obter(ConsultaVendas(90000001, situacoes=frozenset({"fechada"}))) is resultado
    assert cache.obter(ConsultaVendas(90000001)) is None
    assert (
        cache.obter(ConsultaVendas(90000001, situacoes=frozenset({"fechada"}), cliente="x")) is None
    )


def test_guardar_de_novo_troca_o_valor_e_renova_o_prazo(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio)
    consulta = ConsultaVendas(90000001)
    cache.guardar(consulta, _resultado(relogio))
    relogio.avancar(200)
    novo = _resultado(relogio)
    cache.guardar(consulta, novo)
    relogio.avancar(200)
    assert cache.obter(consulta) is novo


def test_acima_do_maximo_sai_o_mais_antigo(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo=2)
    consultas = [ConsultaVendas(90000001 + i) for i in range(3)]
    for consulta in consultas:
        cache.guardar(consulta, _resultado(relogio, consulta.reserva or 0))
        relogio.avancar(1)
    assert cache.obter(consultas[0]) is None
    assert cache.obter(consultas[1]) is not None
    assert cache.obter(consultas[2]) is not None


def test_guardar_de_novo_conta_como_o_mais_novo(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo=2)
    a, b, c = (ConsultaVendas(90000001 + i) for i in range(3))
    cache.guardar(a, _resultado(relogio))
    cache.guardar(b, _resultado(relogio))
    cache.guardar(a, _resultado(relogio))  # a passa a ser o mais novo
    cache.guardar(c, _resultado(relogio))
    assert cache.obter(b) is None
    assert cache.obter(a) is not None
    assert cache.obter(c) is not None


def test_guardar_descarta_os_vencidos_sem_que_ninguem_leia(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo=10)
    cache.guardar(ConsultaVendas(90000001), _resultado(relogio))
    relogio.avancar(100)
    cache.guardar(ConsultaVendas(90000002), _resultado(relogio))
    relogio.avancar(200)  # o primeiro tem 300 s (vencido); o segundo, 200 s
    cache.guardar(ConsultaVendas(90000003), _resultado(relogio))
    assert len(cache) == 2
    assert cache.obter(ConsultaVendas(90000002)) is not None


def test_o_maximo_vale_depois_de_descartar_os_vencidos(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo=2)
    cache.guardar(ConsultaVendas(90000001), _resultado(relogio))
    relogio.avancar(300)
    cache.guardar(ConsultaVendas(90000002), _resultado(relogio))
    cache.guardar(ConsultaVendas(90000003), _resultado(relogio))
    cache.guardar(ConsultaVendas(90000004), _resultado(relogio))
    assert len(cache) == 2
    assert cache.obter(ConsultaVendas(90000002)) is None
    assert cache.obter(ConsultaVendas(90000004)) is not None


def test_validade_zero_nao_guarda_nada(relogio: RelogioFixo) -> None:
    cache = CacheResultados(0, relogio)
    consulta = ConsultaVendas(90000001)
    cache.guardar(consulta, _resultado(relogio))
    assert len(cache) == 0
    assert cache.obter(consulta) is None


def _com_linhas(relogio: RelogioFixo, n: int) -> ResultadoConsulta:
    # model_copy não revalida: para o orçamento só importa quantas linhas há
    return _resultado(relogio).model_copy(update={"vendas": [object()] * n})


def test_acima_do_orcamento_de_linhas_saem_os_mais_antigos(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo_linhas=10)
    a, b, c = (ConsultaVendas(90000001 + i) for i in range(3))
    for consulta in (a, b, c):
        cache.guardar(consulta, _com_linhas(relogio, 4))
    assert cache.obter(a) is None
    assert cache.obter(b) is not None
    assert cache.obter(c) is not None
    assert cache.linhas == 8


def test_resultado_maior_que_o_orcamento_nao_e_guardado(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo_linhas=10)
    a, b = (ConsultaVendas(90000001 + i) for i in range(2))
    cache.guardar(a, _com_linhas(relogio, 4))
    cache.guardar(b, _com_linhas(relogio, 11))
    assert cache.obter(b) is None
    assert cache.obter(a) is not None
    assert cache.linhas == 4


def test_guardar_de_novo_nao_conta_em_dobro(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo_linhas=10)
    a = ConsultaVendas(90000001)
    cache.guardar(a, _com_linhas(relogio, 6))
    cache.guardar(a, _com_linhas(relogio, 6))
    assert len(cache) == 1
    assert cache.linhas == 6


def test_regravar_com_resultado_grande_demais_apaga_o_antigo(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo_linhas=10)
    a = ConsultaVendas(90000001)
    cache.guardar(a, _com_linhas(relogio, 4))
    cache.guardar(a, _com_linhas(relogio, 11))
    assert cache.obter(a) is None
    assert cache.linhas == 0


def test_vencidos_devolvem_o_orcamento(relogio: RelogioFixo) -> None:
    cache = CacheResultados(300, relogio, maximo_linhas=10)
    a, b = (ConsultaVendas(90000001 + i) for i in range(2))
    cache.guardar(a, _com_linhas(relogio, 8))
    relogio.avancar(300)
    assert cache.obter(a) is None
    cache.guardar(b, _com_linhas(relogio, 8))
    assert cache.linhas == 8
