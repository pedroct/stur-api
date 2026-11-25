"""Modelo da venda da AGI. GERADO por scripts/gerar_modelos.py: não editar à mão.

Só nomes e tipos do dicionário de campos. Todo campo é opcional; campo novo é aceito.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ApartamentoAgi(BaseModel):
    """Objeto da AGI em `detalheItem[].apartamentos[]`."""

    model_config = ConfigDict(extra="allow")

    idTipoApto: int | None = None
    qtde: int | None = None
    qtdeDiarias: int | None = None
    tipoApartamento: str | None = None
    vlrBalcao: Decimal | None = None
    vlrDiaria: Decimal | None = None
    vlrDiariaP: Decimal | None = None


class TaxaServicoAgi(BaseModel):
    """Objeto da AGI em `detalheItem[].taxas[]`."""

    model_config = ConfigDict(extra="allow")

    descricaotaxa: str | None = None
    vlrCliente: Decimal | None = None
    vlrFornec: Decimal | None = None


class ServicoAgi(BaseModel):
    """Objeto da AGI em `detalheItem[]`."""

    model_config = ConfigDict(extra="allow")

    acomodacoesePassageiros: str | None = None
    apartamentos: list[ApartamentoAgi] | None = None
    bilhete: str | None = None
    categHotel: str | None = None
    celularpax: str | None = None
    comisSobreTxEmb: Decimal | None = None
    comisSobreTxEmbMoedaOriginal: Decimal | None = None
    confirmadopor: str | None = None
    cpfPax: str | None = None
    datadeconfirmacao: str | None = None
    descricao: str | None = None
    descricaoSiglaTipoPax: str | None = None
    doctoPax: str | None = None
    dtCambio: str | None = None
    dtCambiop: str | None = None
    dtDevolucao: str | None = None
    dtEntrada: str | None = None
    dtInicio: str | None = None
    dtRetirada: str | None = None
    dtSaida: str | None = None
    dtTermino: str | None = None
    emailpax: str | None = None
    horaDevolucao: str | None = None
    horaRetirada: str | None = None
    id: str | None = None
    idPaisPassaporte: int | None = None
    localDevolucao: str | None = None
    localRetirada: str | None = None
    matriculaFunc: str | None = None
    motivoViagem: str | None = None
    nomePax: str | None = None
    nomePaxCompleto: str | None = None
    numeroOS: str | None = None
    numeroPassaporte: str | None = None
    numeroVC: str | None = None
    numeroViagem: str | None = None
    numerodeconfirmacao: str | None = None
    observacao: str | None = None
    observacaoInterna: str | None = None
    perDesconto: Decimal | None = None
    perOverRep: Decimal | None = None
    perTaxas: Decimal | None = None
    perTaxasP: Decimal | None = None
    percComisRecebida: Decimal | None = None
    percComisRepassada: Decimal | None = None
    percDescontoAcordo: Decimal | None = None
    percTxFaturamento: Decimal | None = None
    qtde: int | None = None
    qtdeDiarias: int | None = None
    regime: str | None = None
    rotaProdutoFT: str | None = None
    siglaMoedaTarifa: str | None = None
    siglaMoedaTarifap: str | None = None
    siglaMoedaTaxaServico: str | None = None
    taxas: list[TaxaServicoAgi] | None = None
    tipoViagem: str | None = None
    veiculo: str | None = None
    vlrApliRec: Decimal | None = None
    vlrCambio: Decimal | None = None
    vlrCambioTxServico: Decimal | None = None
    vlrCambiop: Decimal | None = None
    vlrComirecMoedaOriginal: Decimal | None = None
    vlrComisEmissorExterno: Decimal | None = None
    vlrComisRecebida: Decimal | None = None
    vlrComisRepassada: Decimal | None = None
    vlrComisRepassadaMoedaOriginal: Decimal | None = None
    vlrComissaoAuxiliar: Decimal | None = None
    vlrComissaoCoordenador: Decimal | None = None
    vlrComissaoEmissor: Decimal | None = None
    vlrComissaoPromotor: Decimal | None = None
    vlrCustoOperacional: Decimal | None = None
    vlrDesconto: Decimal | None = None
    vlrDescontoAcordo: Decimal | None = None
    vlrDescontoAcordoMoedaOriginal: Decimal | None = None
    vlrDescontoMoedaOriginal: Decimal | None = None
    vlrFeePagar: Decimal | None = None
    vlrFeePagarMoedaOriginal: Decimal | None = None
    vlrOverRec: Decimal | None = None
    vlrOverRecMoedaOriginal: Decimal | None = None
    vlrOverRep: Decimal | None = None
    vlrOverRepMoedaOriginal: Decimal | None = None
    vlrTarCheio: Decimal | None = None
    vlrTarCheiop: Decimal | None = None
    vlrTarifa: Decimal | None = None
    vlrTarifaCheia: Decimal | None = None
    vlrTarifaOficial: Decimal | None = None
    vlrTarifaOficialTotal: Decimal | None = None
    vlrTarifaOficialTotalp: Decimal | None = None
    vlrTarifaOficialp: Decimal | None = None
    vlrTarifaTotal: Decimal | None = None
    vlrTarifaTotalp: Decimal | None = None
    vlrTarifap: Decimal | None = None
    vlrTaxas: Decimal | None = None
    vlrTaxasMoedaOriginal: Decimal | None = None
    vlrTaxasP: Decimal | None = None
    vlrTaxasPMoedaOriginal: Decimal | None = None
    vlrTxDU: Decimal | None = None
    vlrTxDUMoedaOriginal: Decimal | None = None
    vlrTxDURepassada: Decimal | None = None
    vlrTxDURepassadaMoedaOriginal: Decimal | None = None
    vlrTxEmb: Decimal | None = None
    vlrTxEmbp: Decimal | None = None
    vlrTxEmbpMoedaOriginal: Decimal | None = None
    vlrTxExt: Decimal | None = None
    vlrTxExtMoedaOriginal: Decimal | None = None
    vlrTxExtP: Decimal | None = None
    vlrTxExtPMoedaOriginal: Decimal | None = None
    vlrTxFaturamento: Decimal | None = None
    vlrTxFaturamentoMoedaOriginal: Decimal | None = None
    vlrTxServico: Decimal | None = None
    vlrTxServicoMoedaOriginal: Decimal | None = None


class TituloVinculadoAgi(BaseModel):
    """Objeto da AGI em `financeiroVinculado.contasPagar[]` e `financeiroVinculado.contasReceber[]`."""

    model_config = ConfigDict(extra="allow")

    docto: str | None = None
    dtemissao: str | None = None
    id: int | None = None


class FinanceiroVinculadoAgi(BaseModel):
    """Objeto da AGI em `financeiroVinculado`."""

    model_config = ConfigDict(extra="allow")

    contasPagar: list[TituloVinculadoAgi] | None = None
    contasReceber: list[TituloVinculadoAgi] | None = None


class PagamentoAgi(BaseModel):
    """Objeto da AGI em `pagamentos[]`."""

    model_config = ConfigDict(extra="allow")

    descricaoForma: str | None = None
    descricaoFormaPagamentoCartao: str | None = None
    documentosFinanceiro: str | None = None
    dtVencto: str | None = None
    ehsinal: bool | None = None
    forma: int | None = None
    idBenificiario: int | None = None
    moedaOriginal: str | None = None
    nomeBenificiario: str | None = None
    numeroCartaoMascarado: str | None = None
    qtParcelasCartao: int | None = None
    uniqueid: int | None = None
    valor: Decimal | None = None
    valorLiquido: Decimal | None = None
    valorLiquidoMoedaOriginal: Decimal | None = None
    valorMoedaOriginal: Decimal | None = None
    vlrCambio: Decimal | None = None
    vlrTxAdministrativa: Decimal | None = None
    vlrTxAdministrativaMoedaOriginal: Decimal | None = None
    vlrTxAdministrativaRepassada: Decimal | None = None
    vlrTxAdministrativaRepassadaMoedaOriginal: Decimal | None = None


class RecebimentoAgi(BaseModel):
    """Objeto da AGI em `recebimentos[]`."""

    model_config = ConfigDict(extra="allow")

    cartaoRepassadoAoFornecedor: bool | None = None
    descricaoCCustoCliente: str | None = None
    descricaoForma: str | None = None
    documentosFinanceiro: str | None = None
    dtVencto: str | None = None
    ehsinal: bool | None = None
    forma: int | None = None
    idPagante: int | None = None
    moedaOriginal: str | None = None
    nomePagante: str | None = None
    numNotaCredito: str | None = None
    numNotaDebito: str | None = None
    numRecebCartaoCredito: str | None = None
    numRecibo: str | None = None
    numeroCartaoMascarado: str | None = None
    siglaCCustoCliente: str | None = None
    uniqueid: int | None = None
    valor: Decimal | None = None
    valorLiquido: Decimal | None = None
    valorLiquidoMoedaOriginal: Decimal | None = None
    valorMoedaOriginal: Decimal | None = None
    vlrCambio: Decimal | None = None
    vlrRetTarifa: Decimal | None = None
    vlrRetTxDU: Decimal | None = None
    vlrRetTxEmb: Decimal | None = None
    vlrRetTxExtra: Decimal | None = None
    vlrRetTxServ: Decimal | None = None
    vlrTxAdministrativa: Decimal | None = None
    vlrTxAdministrativaMoedaOriginal: Decimal | None = None
    vlrTxAdministrativaRepassada: Decimal | None = None
    vlrTxAdministrativaRepassadaMoedaOriginal: Decimal | None = None


class ReembolsoVinculadoAgi(BaseModel):
    """Objeto da AGI em `reembolsoVinculado[]`."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    idDetalheItem: str | None = None
    idReservaVinculada: int | None = None
    nomePax: str | None = None
    numeroSR: str | None = None


class SistemaExternoAgi(BaseModel):
    """Objeto da AGI em `sistemaExterno`."""

    model_config = ConfigDict(extra="allow")

    idSistema: int | None = None
    idVenda: str | None = None
    sistema: str | None = None


class LocalTrechoAgi(BaseModel):
    """Objeto da AGI em `trechos[].destino` e `trechos[].origem`."""

    model_config = ConfigDict(extra="allow")

    aeroporto: str | None = None
    cidade: str | None = None
    fusoHorario: str | None = None
    pais: str | None = None
    sigla: str | None = None


class TrechoAgi(BaseModel):
    """Objeto da AGI em `trechos[]`."""

    model_config = ConfigDict(extra="allow")

    cia: str | None = None
    classe: str | None = None
    conexao: str | None = None
    destino: LocalTrechoAgi | None = None
    dtChegada: str | None = None
    dtPartida: str | None = None
    farebase: str | None = None
    localizador: str | None = None
    origem: LocalTrechoAgi | None = None
    segmento: int | None = None
    status: str | None = None
    voo: str | None = None


class VendaAgi(BaseModel):
    """Venda da AGI: cada item da lista `vendas` da resposta."""

    model_config = ConfigDict(extra="allow")

    atividade: str | None = None
    camposGerenciais: list[Any] | None = None
    categoriaproduto: str | None = None
    chaveimportacao: str | None = None
    classificacaoproduto: str | None = None
    destino: str | None = None
    detalheItem: list[ServicoAgi] | None = None
    dtalteracao: str | None = None
    dtalteracaovinculado: str | None = None
    dtcancelamento: str | None = None
    dtconfirmacao: str | None = None
    dtcriacao: str | None = None
    dtemissao: str | None = None
    dtreabertura: str | None = None
    dtreativacao: str | None = None
    file: str | None = None
    financeiroVinculado: FinanceiroVinculadoAgi | None = None
    grupocliente: str | None = None
    idAuxiliar: int | None = None
    idCentrocustos: int | None = None
    idCliente: int | None = None
    idDepSetCli: int | None = None
    idPromotor: int | None = None
    idcCustoCliente: int | None = None
    idemissor: int | None = None
    idfilial: int | None = None
    idfornec: int | None = None
    idfornec2: int | None = None
    idproduto: int | None = None
    idreserva: int | None = None
    idreservavinculadafee: int | None = None
    intinerario: str | None = None
    margemLucroBruta: Decimal | None = None
    midiaOrigem: str | None = None
    nomeAutorizador: str | None = None
    nomeAuxiliar: str | None = None
    nomeCCustoCliente: str | None = None
    nomeCenctroCustos: str | None = None
    nomeCoordenador: str | None = None
    nomeDeptoSetorCli: str | None = None
    nomeEmissor: str | None = None
    nomeFilial: str | None = None
    nomePromotor: str | None = None
    nomeSolicitante: str | None = None
    nomearquivo: str | None = None
    nomecliente: str | None = None
    nomefornec: str | None = None
    nomefornec2: str | None = None
    nomeproduto: str | None = None
    pagamentos: list[PagamentoAgi] | None = None
    projeto: str | None = None
    recebimentos: list[RecebimentoAgi] | None = None
    reembolsoVinculado: list[ReembolsoVinculadoAgi] | None = None
    reserva: int | None = None
    siglaCCustoCliente: str | None = None
    sistemaExterno: SistemaExternoAgi | None = None
    situacaoFinanceiroRecebimento: str | None = None
    status: str | None = None
    taxasAdministrativas: Decimal | None = None
    taxasAdministrativasRepassadas: Decimal | None = None
    tipoVenda: str | None = None
    tiporegistro: str | None = None
    totalAPagarCliente: Decimal | None = None
    totalAPagarFornec: Decimal | None = None
    totalAReceberCliente: Decimal | None = None
    totalAReceberFornecedor: Decimal | None = None
    totalCliente: Decimal | None = None
    totalFornecedor: Decimal | None = None
    totalPagoCliente: Decimal | None = None
    totalPagoFornec: Decimal | None = None
    totalRecebidoCliente: Decimal | None = None
    totalRecebidoFornec: Decimal | None = None
    trechos: list[TrechoAgi] | None = None


# Caminhos de folha conhecidos (`[]` no lugar dos índices); o resto é desconhecido.
CAMINHOS_CONHECIDOS: frozenset[str] = frozenset(
    {
        "atividade",
        "camposGerenciais",
        "categoriaproduto",
        "chaveimportacao",
        "classificacaoproduto",
        "destino",
        "detalheItem[].acomodacoesePassageiros",
        "detalheItem[].apartamentos[].idTipoApto",
        "detalheItem[].apartamentos[].qtde",
        "detalheItem[].apartamentos[].qtdeDiarias",
        "detalheItem[].apartamentos[].tipoApartamento",
        "detalheItem[].apartamentos[].vlrBalcao",
        "detalheItem[].apartamentos[].vlrDiaria",
        "detalheItem[].apartamentos[].vlrDiariaP",
        "detalheItem[].bilhete",
        "detalheItem[].categHotel",
        "detalheItem[].celularpax",
        "detalheItem[].comisSobreTxEmb",
        "detalheItem[].comisSobreTxEmbMoedaOriginal",
        "detalheItem[].confirmadopor",
        "detalheItem[].cpfPax",
        "detalheItem[].datadeconfirmacao",
        "detalheItem[].descricao",
        "detalheItem[].descricaoSiglaTipoPax",
        "detalheItem[].doctoPax",
        "detalheItem[].dtCambio",
        "detalheItem[].dtCambiop",
        "detalheItem[].dtDevolucao",
        "detalheItem[].dtEntrada",
        "detalheItem[].dtInicio",
        "detalheItem[].dtRetirada",
        "detalheItem[].dtSaida",
        "detalheItem[].dtTermino",
        "detalheItem[].emailpax",
        "detalheItem[].horaDevolucao",
        "detalheItem[].horaRetirada",
        "detalheItem[].id",
        "detalheItem[].idPaisPassaporte",
        "detalheItem[].localDevolucao",
        "detalheItem[].localRetirada",
        "detalheItem[].matriculaFunc",
        "detalheItem[].motivoViagem",
        "detalheItem[].nomePax",
        "detalheItem[].nomePaxCompleto",
        "detalheItem[].numeroOS",
        "detalheItem[].numeroPassaporte",
        "detalheItem[].numeroVC",
        "detalheItem[].numeroViagem",
        "detalheItem[].numerodeconfirmacao",
        "detalheItem[].observacao",
        "detalheItem[].observacaoInterna",
        "detalheItem[].perDesconto",
        "detalheItem[].perOverRep",
        "detalheItem[].perTaxas",
        "detalheItem[].perTaxasP",
        "detalheItem[].percComisRecebida",
        "detalheItem[].percComisRepassada",
        "detalheItem[].percDescontoAcordo",
        "detalheItem[].percTxFaturamento",
        "detalheItem[].qtde",
        "detalheItem[].qtdeDiarias",
        "detalheItem[].regime",
        "detalheItem[].rotaProdutoFT",
        "detalheItem[].siglaMoedaTarifa",
        "detalheItem[].siglaMoedaTarifap",
        "detalheItem[].siglaMoedaTaxaServico",
        "detalheItem[].taxas[].descricaotaxa",
        "detalheItem[].taxas[].vlrCliente",
        "detalheItem[].taxas[].vlrFornec",
        "detalheItem[].tipoViagem",
        "detalheItem[].veiculo",
        "detalheItem[].vlrApliRec",
        "detalheItem[].vlrCambio",
        "detalheItem[].vlrCambioTxServico",
        "detalheItem[].vlrCambiop",
        "detalheItem[].vlrComirecMoedaOriginal",
        "detalheItem[].vlrComisEmissorExterno",
        "detalheItem[].vlrComisRecebida",
        "detalheItem[].vlrComisRepassada",
        "detalheItem[].vlrComisRepassadaMoedaOriginal",
        "detalheItem[].vlrComissaoAuxiliar",
        "detalheItem[].vlrComissaoCoordenador",
        "detalheItem[].vlrComissaoEmissor",
        "detalheItem[].vlrComissaoPromotor",
        "detalheItem[].vlrCustoOperacional",
        "detalheItem[].vlrDesconto",
        "detalheItem[].vlrDescontoAcordo",
        "detalheItem[].vlrDescontoAcordoMoedaOriginal",
        "detalheItem[].vlrDescontoMoedaOriginal",
        "detalheItem[].vlrFeePagar",
        "detalheItem[].vlrFeePagarMoedaOriginal",
        "detalheItem[].vlrOverRec",
        "detalheItem[].vlrOverRecMoedaOriginal",
        "detalheItem[].vlrOverRep",
        "detalheItem[].vlrOverRepMoedaOriginal",
        "detalheItem[].vlrTarCheio",
        "detalheItem[].vlrTarCheiop",
        "detalheItem[].vlrTarifa",
        "detalheItem[].vlrTarifaCheia",
        "detalheItem[].vlrTarifaOficial",
        "detalheItem[].vlrTarifaOficialTotal",
        "detalheItem[].vlrTarifaOficialTotalp",
        "detalheItem[].vlrTarifaOficialp",
        "detalheItem[].vlrTarifaTotal",
        "detalheItem[].vlrTarifaTotalp",
        "detalheItem[].vlrTarifap",
        "detalheItem[].vlrTaxas",
        "detalheItem[].vlrTaxasMoedaOriginal",
        "detalheItem[].vlrTaxasP",
        "detalheItem[].vlrTaxasPMoedaOriginal",
        "detalheItem[].vlrTxDU",
        "detalheItem[].vlrTxDUMoedaOriginal",
        "detalheItem[].vlrTxDURepassada",
        "detalheItem[].vlrTxDURepassadaMoedaOriginal",
        "detalheItem[].vlrTxEmb",
        "detalheItem[].vlrTxEmbp",
        "detalheItem[].vlrTxEmbpMoedaOriginal",
        "detalheItem[].vlrTxExt",
        "detalheItem[].vlrTxExtMoedaOriginal",
        "detalheItem[].vlrTxExtP",
        "detalheItem[].vlrTxExtPMoedaOriginal",
        "detalheItem[].vlrTxFaturamento",
        "detalheItem[].vlrTxFaturamentoMoedaOriginal",
        "detalheItem[].vlrTxServico",
        "detalheItem[].vlrTxServicoMoedaOriginal",
        "dtalteracao",
        "dtalteracaovinculado",
        "dtcancelamento",
        "dtconfirmacao",
        "dtcriacao",
        "dtemissao",
        "dtreabertura",
        "dtreativacao",
        "file",
        "financeiroVinculado.contasPagar[].docto",
        "financeiroVinculado.contasPagar[].dtemissao",
        "financeiroVinculado.contasPagar[].id",
        "financeiroVinculado.contasReceber[].docto",
        "financeiroVinculado.contasReceber[].dtemissao",
        "financeiroVinculado.contasReceber[].id",
        "grupocliente",
        "idAuxiliar",
        "idCentrocustos",
        "idCliente",
        "idDepSetCli",
        "idPromotor",
        "idcCustoCliente",
        "idemissor",
        "idfilial",
        "idfornec",
        "idfornec2",
        "idproduto",
        "idreserva",
        "idreservavinculadafee",
        "intinerario",
        "margemLucroBruta",
        "midiaOrigem",
        "nomeAutorizador",
        "nomeAuxiliar",
        "nomeCCustoCliente",
        "nomeCenctroCustos",
        "nomeCoordenador",
        "nomeDeptoSetorCli",
        "nomeEmissor",
        "nomeFilial",
        "nomePromotor",
        "nomeSolicitante",
        "nomearquivo",
        "nomecliente",
        "nomefornec",
        "nomefornec2",
        "nomeproduto",
        "pagamentos[].descricaoForma",
        "pagamentos[].descricaoFormaPagamentoCartao",
        "pagamentos[].documentosFinanceiro",
        "pagamentos[].dtVencto",
        "pagamentos[].ehsinal",
        "pagamentos[].forma",
        "pagamentos[].idBenificiario",
        "pagamentos[].moedaOriginal",
        "pagamentos[].nomeBenificiario",
        "pagamentos[].numeroCartaoMascarado",
        "pagamentos[].qtParcelasCartao",
        "pagamentos[].uniqueid",
        "pagamentos[].valor",
        "pagamentos[].valorLiquido",
        "pagamentos[].valorLiquidoMoedaOriginal",
        "pagamentos[].valorMoedaOriginal",
        "pagamentos[].vlrCambio",
        "pagamentos[].vlrTxAdministrativa",
        "pagamentos[].vlrTxAdministrativaMoedaOriginal",
        "pagamentos[].vlrTxAdministrativaRepassada",
        "pagamentos[].vlrTxAdministrativaRepassadaMoedaOriginal",
        "projeto",
        "recebimentos[].cartaoRepassadoAoFornecedor",
        "recebimentos[].descricaoCCustoCliente",
        "recebimentos[].descricaoForma",
        "recebimentos[].documentosFinanceiro",
        "recebimentos[].dtVencto",
        "recebimentos[].ehsinal",
        "recebimentos[].forma",
        "recebimentos[].idPagante",
        "recebimentos[].moedaOriginal",
        "recebimentos[].nomePagante",
        "recebimentos[].numNotaCredito",
        "recebimentos[].numNotaDebito",
        "recebimentos[].numRecebCartaoCredito",
        "recebimentos[].numRecibo",
        "recebimentos[].numeroCartaoMascarado",
        "recebimentos[].siglaCCustoCliente",
        "recebimentos[].uniqueid",
        "recebimentos[].valor",
        "recebimentos[].valorLiquido",
        "recebimentos[].valorLiquidoMoedaOriginal",
        "recebimentos[].valorMoedaOriginal",
        "recebimentos[].vlrCambio",
        "recebimentos[].vlrRetTarifa",
        "recebimentos[].vlrRetTxDU",
        "recebimentos[].vlrRetTxEmb",
        "recebimentos[].vlrRetTxExtra",
        "recebimentos[].vlrRetTxServ",
        "recebimentos[].vlrTxAdministrativa",
        "recebimentos[].vlrTxAdministrativaMoedaOriginal",
        "recebimentos[].vlrTxAdministrativaRepassada",
        "recebimentos[].vlrTxAdministrativaRepassadaMoedaOriginal",
        "reembolsoVinculado[].id",
        "reembolsoVinculado[].idDetalheItem",
        "reembolsoVinculado[].idReservaVinculada",
        "reembolsoVinculado[].nomePax",
        "reembolsoVinculado[].numeroSR",
        "reserva",
        "siglaCCustoCliente",
        "sistemaExterno.idSistema",
        "sistemaExterno.idVenda",
        "sistemaExterno.sistema",
        "situacaoFinanceiroRecebimento",
        "status",
        "taxasAdministrativas",
        "taxasAdministrativasRepassadas",
        "tipoVenda",
        "tiporegistro",
        "totalAPagarCliente",
        "totalAPagarFornec",
        "totalAReceberCliente",
        "totalAReceberFornecedor",
        "totalCliente",
        "totalFornecedor",
        "totalPagoCliente",
        "totalPagoFornec",
        "totalRecebidoCliente",
        "totalRecebidoFornec",
        "trechos[].cia",
        "trechos[].classe",
        "trechos[].conexao",
        "trechos[].destino.aeroporto",
        "trechos[].destino.cidade",
        "trechos[].destino.fusoHorario",
        "trechos[].destino.pais",
        "trechos[].destino.sigla",
        "trechos[].dtChegada",
        "trechos[].dtPartida",
        "trechos[].farebase",
        "trechos[].localizador",
        "trechos[].origem.aeroporto",
        "trechos[].origem.cidade",
        "trechos[].origem.fusoHorario",
        "trechos[].origem.pais",
        "trechos[].origem.sigla",
        "trechos[].segmento",
        "trechos[].status",
        "trechos[].voo",
    }
)
