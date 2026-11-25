"""Serviço da consulta: busca na AGI, cálculos do domínio e montagem do contrato.

Nada aqui grava em log os textos de filtro (cliente, fornecedor, emissor) nem as vendas.
"""

import asyncio
from collections.abc import Iterable
from dataclasses import asdict
from datetime import date
from typing import Any

import httpx

from stur_api.agi.campos import campos_desconhecidos, validar_venda
from stur_api.agi.cliente import ClienteAgi, FiltroAgi, janela_larga
from stur_api.agi.json_cru import serializar_cru
from stur_api.agi.modelos import VendaAgi
from stur_api.config import Configuracao
from stur_api.contrato.calculos import (
    ContaServico,
    EstadoServico,
    Itinerario,
    LancamentoCalculado,
    ResumoResultado,
    ResumoVenda,
    TotaisReserva,
    Verificacao,
)
from stur_api.contrato.comum import SituacaoApiStur
from stur_api.contrato.consulta import (
    ConsultaEcoada,
    LinhaResultado,
    Parametros,
    ResultadoConsulta,
    VinculoDoFee,
)
from stur_api.contrato.venda import (
    Aviso,
    CalculosVenda,
    CodigoAviso,
    ReembolsoVinculado,
    Reserva,
    ReservaConsultada,
    TotaisServicos,
    VendaConsultada,
    VendaDaReserva,
    VendaVinculada,
    Vinculos,
)
from stur_api.dominio import contas as dominio_contas
from stur_api.dominio import lancamentos as dominio_lancamentos
from stur_api.dominio import vendas as dominio_vendas
from stur_api.dominio.consulta import ConsultaVendas, filtro_agi, validar_consulta
from stur_api.dominio.datas import ler_data_hora
from stur_api.dominio.estado_servico import estado_do_servico
from stur_api.dominio.itinerario import montar_itinerario
from stur_api.dominio.resultado import (
    aplicar_filtros,
    ordenar_resultado,
    resumir_resultado,
    vendas_no_resultado,
)
from stur_api.dominio.textos import normalizar
from stur_api.erros import ApiSturAcessoRecusado, ErroAplicacao, VendaNaoEncontrada
from stur_api.relogio import Relogio
from stur_api.servicos.cache import CacheResultados
from stur_api.servicos.data_copia import DataDaCopia

BUSCAS_POR_ID_SIMULTANEAS = 4  # reembolsos de outro número: chamadas à AGI ao mesmo tempo


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
        dados_ate = await self._dados_ate(vendas)
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
        except (ErroAplicacao, httpx.HTTPError):
            # sem resposta, resposta que não serve para entrar, ou erro do httpx que o cliente
            # não traduz (R18)
            return "sem_resposta"
        return "ok"

    # --- reserva, venda e dado cru: sem cache, cada abertura é uma consulta nova (PRD RF-10) ---

    async def abrir_reserva(self, numero: int) -> ReservaConsultada:
        """Todas as vendas do número numa chamada à AGI. Número sem vendas: a lista vazia."""
        consultado_em = self._relogio.agora()
        hoje = consultado_em.date()
        vendas = [validar_venda(v) for v in await self._vendas_do_numero(numero, hoje)]
        return ReservaConsultada(
            numero=numero,
            consultado_em=consultado_em,
            dados_do_stur_ate=await self._dados_ate(vendas),
            reserva=_reserva(
                numero, dominio_vendas.ordenar_por_lancamento(vendas), self._config, hoje
            ),
        )

    async def abrir_venda(self, numero: int, idreserva: int) -> VendaConsultada:
        """A venda com os cálculos, a reserva em volta e os vínculos.

        A chamada pelo número traz a venda, as outras do número e o fee; só o reembolso ligado
        a uma venda de outro número custa mais uma chamada, por id. `idreserva` fora do número
        levanta `VendaNaoEncontrada` (404).
        """
        consultado_em = self._relogio.agora()
        hoje = consultado_em.date()
        crus = await self._vendas_do_numero(numero, hoje)
        vendas = [validar_venda(v) for v in crus]  # o dado cru fica à parte, como a AGI mandou
        indice = next((i for i, v in enumerate(vendas) if v.idreserva == idreserva), None)
        if indice is None:
            raise VendaNaoEncontrada()
        venda = vendas[indice]
        ordenadas = dominio_vendas.ordenar_por_lancamento(vendas)
        return VendaConsultada(
            consultado_em=consultado_em,
            dados_do_stur_ate=await self._dados_ate(vendas),
            venda=venda,
            calculos=_calculos(venda, self._config, hoje),
            reserva=_reserva(numero, ordenadas, self._config, hoje),
            posicao=next(p for p, v in enumerate(ordenadas, start=1) if v.idreserva == idreserva),
            vinculos=Vinculos(
                fee=_fee(venda, ordenadas),
                reembolsos=await self._reembolsos(venda, ordenadas, hoje),
            ),
            campos_desconhecidos=campos_desconhecidos(crus[indice]),
        )

    async def dado_cru(self, numero: int, idreserva: int) -> str:
        """O JSON da venda como a AGI devolveu: números exatos e a ordem das chaves.

        Não passa pelo modelo: a venda aparece mesmo com um campo que mudou de tipo, que é
        quando o dado cru mais serve (RF-07, para diagnosticar).
        """
        crus = await self._vendas_do_numero(numero, self._relogio.agora().date())
        cru = next((v for v in crus if v.get("idreserva") == idreserva), None)
        if cru is None:
            raise VendaNaoEncontrada()
        return serializar_cru(cru)

    async def _vendas_do_numero(self, numero: int, hoje: date) -> list[dict[str, Any]]:
        """Uma chamada pelo filtro `Reserva`, na janela larga (roteiro, decisão 2)."""
        filtro = filtro_agi(ConsultaVendas(reserva=numero), self._config, hoje)
        return await self._cliente.buscar_vendas(filtro)

    async def _dados_ate(self, vendas: list[VendaAgi]) -> str | None:
        """A data da cópia vista nas vendas; sem venda datada, a guardada ou a consulta pequena."""
        return self._data_copia.registrar(vendas) or await self._data_copia.obter()

    async def _reembolsos(
        self, venda: VendaAgi, ordenadas: list[VendaAgi], hoje: date
    ) -> list[ReembolsoVinculado]:
        """Cada reembolso com a venda a que se liga: do número, sem chamada; de fora, por id."""
        itens = venda.reembolsoVinculado or []
        do_numero = {v.idreserva for v in ordenadas}
        de_fora: list[int] = []
        for item in itens:
            vinculada = item.idReservaVinculada
            if vinculada and vinculada not in do_numero and vinculada not in de_fora:
                de_fora.append(vinculada)
        buscadas = await self._vendas_por_id(de_fora, hoje)

        reembolsos: list[ReembolsoVinculado] = []
        for item in itens:
            vinculada = item.idReservaVinculada
            venda_vinculada: VendaVinculada | None = None
            if vinculada and vinculada in do_numero:
                venda_vinculada = _vinculada_do_numero(vinculada, ordenadas)
            elif vinculada and (achada := buscadas.get(vinculada)) is not None:
                venda_vinculada = _vinculada(achada, posicao=None, quantidade=None)
            reembolsos.append(
                ReembolsoVinculado(
                    id=item.id,
                    numero_sr=item.numeroSR,
                    nome_pax=item.nomePax,
                    venda=venda_vinculada,
                )
            )
        return reembolsos

    async def _vendas_por_id(self, ids: list[int], hoje: date) -> dict[int, VendaAgi | None]:
        """Uma chamada por id na janela larga, até 4 ao mesmo tempo. A que falha fica `None`."""
        inicio, fim = janela_larga(self._config, hoje)
        limite = asyncio.Semaphore(BUSCAS_POR_ID_SIMULTANEAS)

        async def buscar(id_venda: int) -> VendaAgi | None:
            filtro = FiltroAgi(
                tipo_data="EMISSAO", data_inicial=inicio, data_final=fim, id=id_venda
            )
            async with limite:
                try:
                    achadas = [validar_venda(v) for v in await self._cliente.buscar_vendas(filtro)]
                except (ErroAplicacao, httpx.HTTPError):
                    return None  # o reembolso fica sem a venda; a venda aberta não cai
            return next((v for v in achadas if v.idreserva == id_venda), None)

        encontradas = await asyncio.gather(*(buscar(id_venda) for id_venda in ids))
        return dict(zip(ids, encontradas, strict=True))


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


# --- reserva e venda ---


def _lancamentos(
    calculados: list[dominio_lancamentos.LancamentoCalculado],
) -> list[LancamentoCalculado]:
    return [LancamentoCalculado.model_validate(asdict(c)) for c in calculados]


def _reserva(numero: int, ordenadas: list[VendaAgi], config: Configuracao, hoje: date) -> Reserva:
    """A reserva: as vendas na ordem de lançamento, com posição, lançamentos e totais."""
    resumos = [dominio_vendas.resumir(v, config) for v in ordenadas]
    return Reserva(
        numero=numero,
        vendas=[
            VendaDaReserva(
                resumo=ResumoVenda.model_validate(asdict(resumo)),
                posicao=posicao,
                recebimentos=_lancamentos(
                    dominio_lancamentos.situacao_dos_recebimentos(venda, hoje)
                ),
                pagamentos=_lancamentos(dominio_lancamentos.situacao_dos_pagamentos(venda, hoje)),
            )
            for posicao, (venda, resumo) in enumerate(zip(ordenadas, resumos, strict=True), 1)
        ],
        totais=TotaisReserva.model_validate(asdict(dominio_vendas.totais_da_reserva(resumos))),
    )


def _calculos(venda: VendaAgi, config: Configuracao, hoje: date) -> CalculosVenda:
    """Valores calculados da venda (PRD 8.3). `servicos[].indice`: a posição em `detalheItem`."""
    contas = [
        dominio_contas.conta_do_servico(servico, indice, venda.status or "")
        for indice, servico in enumerate(venda.detalheItem or [])
    ]
    verificacao = dominio_contas.verificar_totais(venda, contas, config)
    cliente = sum((c.cliente.total for c in contas), start=dominio_contas.ZERO)
    fornecedor = sum((c.fornecedor.total for c in contas), start=dominio_contas.ZERO)
    margem = sum((c.margem for c in contas), start=dominio_contas.ZERO)
    total_pagamentos = dominio_lancamentos.total_dos_pagamentos(venda)
    itinerario = montar_itinerario(venda.trechos or [], config.corte_trajeto_horas)
    estado = estado_do_servico(venda, hoje)
    tipo = dominio_vendas.tipo_da_venda(venda, config)
    return CalculosVenda(
        tipo=tipo,
        servicos=[ContaServico.model_validate(asdict(c)) for c in contas],
        totais_servicos=TotaisServicos(
            cliente=cliente,
            fornecedor=fornecedor,
            margem=margem,
            percentual_lucro=dominio_contas.percentual_lucro(margem, cliente),
        ),
        percentual_lucro=dominio_contas.percentual_lucro(
            venda.margemLucroBruta or dominio_contas.ZERO, venda.totalCliente or dominio_contas.ZERO
        ),
        verificacao=Verificacao.model_validate(asdict(verificacao)),
        recebimentos=_lancamentos(dominio_lancamentos.situacao_dos_recebimentos(venda, hoje)),
        pagamentos=_lancamentos(dominio_lancamentos.situacao_dos_pagamentos(venda, hoje)),
        total_pagamentos=total_pagamentos,
        # PRD 8.3: os dois valores e a diferença, sem aviso; negativa é pagamento não lançado
        diferenca_pagamentos_fornecedor=total_pagamentos
        - (venda.totalFornecedor or dominio_contas.ZERO),
        itinerario=None if itinerario is None else Itinerario.model_validate(asdict(itinerario)),
        estado_servico=None if estado is None else EstadoServico.model_validate(asdict(estado)),
        avisos=_avisos(venda, contas, verificacao, tipo),
    )


def _siglas(siglas: Iterable[str]) -> list[str]:
    """Sem repetir, na ordem em que aparecem nos serviços."""
    return list(dict.fromkeys(siglas))


def _avisos(
    venda: VendaAgi,
    contas: list[dominio_contas.ContaServico],
    verificacao: dominio_contas.Verificacao,
    tipo: dominio_vendas.TipoVenda,
) -> list[Aviso]:
    """Avisos do topo da venda, atenção antes de informação (IA 9.5).

    O único de atenção é a conta que não fecha; depois vêm os de informação, na ordem da IA 9.5
    (moeda estrangeira, moeda com câmbio 1, comissão não apurada, fee) e os de situação
    (cancelada, 9.4; reservada, 9.4b). A comissão não apurada vale só na confirmada: na
    reservada o aviso da reservada a substitui (9.4b), e a cancelada não chega a apurar.
    """
    situacao = normalizar(venda.status or "")
    lados = [lado for c in contas for lado in (c.cliente, c.fornecedor)]
    estrangeiras = _siglas(lado.conversao.sigla for lado in lados if lado.conversao is not None)
    cambio_1 = _siglas(
        lado.sigla_com_cambio_1 for lado in lados if lado.sigla_com_cambio_1 is not None
    )
    regras: list[tuple[CodigoAviso, bool, list[str]]] = [
        ("conta_nao_fecha", not verificacao.fecha, []),
        ("moeda_estrangeira", bool(estrangeiras), estrangeiras),
        ("moeda_cambio_1", bool(cambio_1), cambio_1),
        (
            "comissao_nao_apurada",
            situacao == "CONFIRMADA" and any(c.comissoes_nao_apuradas for c in contas),
            [],
        ),
        ("venda_fee", tipo == "fee", []),
        ("venda_cancelada", situacao == "CANCELADA", []),
        ("venda_reservada", situacao == "RESERVADA", []),
    ]
    return [Aviso(codigo=codigo, siglas=siglas) for codigo, vale, siglas in regras if vale]


def _vinculada(
    venda: VendaAgi, posicao: int | None, quantidade: int | None
) -> VendaVinculada | None:
    if venda.idreserva is None or venda.reserva is None:
        return None  # `validar_venda` já exige os dois; o teste só estreita o tipo
    return VendaVinculada(
        idreserva=venda.idreserva,
        numero=venda.reserva,
        produto=venda.nomeproduto,
        posicao=posicao,
        quantidade=quantidade,
    )


def _vinculada_do_numero(idreserva: int, ordenadas: list[VendaAgi]) -> VendaVinculada | None:
    """A venda do mesmo número, com a posição dela e quantas vendas o número tem."""
    for posicao, outra in enumerate(ordenadas, start=1):
        if outra.idreserva == idreserva:
            return _vinculada(outra, posicao, len(ordenadas))
    return None


def _fee(venda: VendaAgi, ordenadas: list[VendaAgi]) -> VendaVinculada | None:
    """A outra ponta do vínculo de fee, nos dois sentidos (PRD 8.4).

    Procurada só entre as vendas do número: o fee nunca liga números diferentes, e a busca de
    fora custaria uma chamada à AGI. Vínculo que aponta para fora do número fica `None` (o
    `idreservavinculadafee` continua na venda).
    """
    if not venda.idreservavinculadafee:
        return None
    return _vinculada_do_numero(venda.idreservavinculadafee, ordenadas)
