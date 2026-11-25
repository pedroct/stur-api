"""Serviço da consulta: busca na AGI, cálculos do domínio e montagem do contrato.

Nada aqui grava em log os textos de filtro (cliente, fornecedor, emissor) nem as vendas.
"""

from dataclasses import asdict

from stur_api.agi.campos import validar_venda
from stur_api.agi.cliente import ClienteAgi
from stur_api.agi.modelos import VendaAgi
from stur_api.config import Configuracao
from stur_api.contrato.calculos import ResumoResultado
from stur_api.contrato.comum import SituacaoApiStur
from stur_api.contrato.consulta import (
    ConsultaEcoada,
    LinhaResultado,
    Parametros,
    ResultadoConsulta,
    VinculoDoFee,
)
from stur_api.dominio import vendas as dominio_vendas
from stur_api.dominio.consulta import ConsultaVendas, filtro_agi, validar_consulta
from stur_api.dominio.datas import ler_data_hora
from stur_api.dominio.resultado import (
    aplicar_filtros,
    ordenar_resultado,
    resumir_resultado,
    vendas_no_resultado,
)
from stur_api.erros import ApiSturAcessoRecusado, ErroAplicacao
from stur_api.relogio import Relogio
from stur_api.servicos.cache import CacheResultados
from stur_api.servicos.data_copia import DataDaCopia


class ServicoConsulta:
    def __init__(self, config: Configuracao, cliente: ClienteAgi, relogio: Relogio) -> None:
        self._config = config
        self._cliente = cliente
        self._relogio = relogio
        self._cache = CacheResultados(config.cache_resultado_s, relogio)
        # a data da cópia fica guardada pelo mesmo prazo do resultado (5 minutos, PRD 9.3)
        self._data_copia = DataDaCopia(cliente, relogio, config.cache_resultado_s)

    async def consultar_vendas(self, c: ConsultaVendas, atualizar: bool) -> ResultadoConsulta:
        """Valida antes de chamar a AGI; `atualizar` ignora o guardado e guarda o novo."""
        validar_consulta(c, self._config)
        if not atualizar:
            guardado = self._cache.obter(c)
            if guardado is not None:
                return guardado
        consultado_em = self._relogio.agora()
        filtro = filtro_agi(c, self._config, consultado_em.date())
        vendas = [validar_venda(v) for v in await self._cliente.buscar_vendas(filtro)]
        dados_ate = self._data_copia.registrar(vendas) or await self._data_copia.obter()
        resumos = [dominio_vendas.resumir(v, self._config) for v in vendas]
        achados = ordenar_resultado(aplicar_filtros(resumos, c), c)
        resultado = ResultadoConsulta(
            consulta=_consulta_ecoada(c),
            consultado_em=consultado_em,
            dados_do_stur_ate=dados_ate,
            periodo_passa_da_copia=_periodo_passa_da_copia(c, dados_ate),
            vendas=_linhas(achados, vendas),
            resumo=ResumoResultado.model_validate(asdict(resumir_resultado(achados))),
        )
        self._cache.guardar(c, resultado)
        return resultado

    async def parametros(self) -> Parametros:
        return Parametros(
            periodo_maximo_dias=self._config.periodo_maximo_dias,
            linhas_por_pagina=self._config.linhas_por_pagina,
            opcoes_por_pagina=self._config.opcoes_por_pagina,
            tempo_limite_segundos=self._config.agi_tempo_limite_s,
            dados_do_stur_ate=await self._data_copia.obter(),
        )

    async def verificar_api_stur(self) -> SituacaoApiStur:
        """Login de verdade na AGI. Nunca levanta: a saúde da AGI é informação, não erro."""
        try:
            await self._cliente.verificar_acesso()
        except ApiSturAcessoRecusado:
            return "acesso_recusado"
        except ErroAplicacao:
            return "sem_resposta"  # sem resposta ou resposta que não serve para entrar
        return "ok"


def _consulta_ecoada(c: ConsultaVendas) -> ConsultaEcoada:
    return ConsultaEcoada(
        reserva=c.reserva,
        tipo_data=c.tipo_data,
        de=c.de,
        ate=c.ate,
        situacao=sorted(c.situacoes),
        classificacao=sorted(c.classificacoes),
        fornecedor=c.fornecedor,
        cliente=c.cliente,
        emissor=c.emissor,
        janela_larga=c.de is None or c.ate is None,
    )


def _periodo_passa_da_copia(c: ConsultaVendas, dados_ate: str | None) -> bool:
    """O fim do período é depois do dia da cópia (R8): a lista pode estar incompleta."""
    copia = ler_data_hora(dados_ate, "dtalteracaovinculado")
    return copia is not None and c.ate is not None and c.ate > copia.date()


def _linhas(
    achados: list[dominio_vendas.ResumoVenda], vendas: list[VendaAgi]
) -> list[LinhaResultado]:
    """Linhas com quantas vendas do mesmo número estão no resultado e, no fee, a venda dele.

    O produto da venda do fee só vem quando ela está no resultado: buscar a de fora custaria
    uma chamada à AGI por fee (roteiro, decisão 11).
    """
    por_numero = vendas_no_resultado(achados)
    produto_no_resultado = {r.idreserva: r.produto for r in achados if r.idreserva is not None}
    vinculo_do_fee = {
        v.idreserva: v.idreservavinculadafee for v in vendas if v.idreserva is not None
    }
    linhas: list[LinhaResultado] = []
    for r in achados:
        fee: VinculoDoFee | None = None
        if r.tipo == "fee" and r.idreserva is not None:
            vinculada = vinculo_do_fee.get(r.idreserva)
            if vinculada:  # o tipo "fee" já exige o vínculo; o teste só estreita o tipo
                fee = VinculoDoFee(idreserva=vinculada, produto=produto_no_resultado.get(vinculada))
        quantidade = 0 if r.numero is None else por_numero.get(r.numero, 0)
        linhas.append(LinhaResultado(**asdict(r), vendas_no_resultado=quantidade, fee=fee))
    return linhas
