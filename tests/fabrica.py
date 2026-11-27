"""Vendas, serviços, trechos e lançamentos inventados, como a AGI devolve depois de `carregar_json`.

Números já em `Decimal`. Só campos que existem no dicionário da AGI: a venda padrão não tem
nenhum campo desconhecido. Cada chamada monta dicionários novos (os testes podem alterá-los).
"""

from decimal import Decimal
from typing import Any

from stur_api.agi.json_cru import serializar_cru
from stur_api.agi.modelos import ServicoAgi, TrechoAgi, VendaAgi

ZERO = Decimal("0")
UM = Decimal("1")
DATA_PADRAO = "2026-11-01 09:00:00"
VENCIMENTO_PADRAO = "2026-11-30 00:00:00"

# descricaoForma de cada forma, como a AGI escreve (rótulos do sistema, não dados de cliente)
FORMAS_RECEBIMENTO = {0: "Cash", 1: "Faturado", 2: "Cartão", 5: "Crédito ao Cliente"}
FORMAS_PAGAMENTO = {
    0: "Cash",
    1: "Faturado",
    2: "Crédito",
    3: "Cartão de Crédito Agência",
    4: "CreditoLeiKandir",
}


def servico(**campos: Any) -> dict[str, Any]:
    """Serviço em real com todos os termos das fórmulas zerados e câmbio 1."""
    base: dict[str, Any] = {
        "id": "1",
        "nomePax": "PASSAGEIRO EXEMPLO",
        "nomePaxCompleto": "PASSAGEIRO EXEMPLO",
        "siglaMoedaTarifa": "R$",
        "siglaMoedaTarifap": "R$",
        "siglaMoedaTaxaServico": "R$",
        "vlrCambio": UM,
        "vlrCambiop": UM,
        "vlrCambioTxServico": UM,
        "dtCambio": None,
        "dtCambiop": None,
        # cliente
        "vlrTarifaTotal": ZERO,
        "vlrTaxas": ZERO,
        "vlrTxExt": ZERO,
        "vlrTxServico": ZERO,
        "vlrTxEmb": ZERO,
        "vlrTxDU": ZERO,
        "vlrDesconto": ZERO,
        # fornecedor
        "vlrTarifaTotalp": ZERO,
        "vlrTaxasP": ZERO,
        "vlrTxExtP": ZERO,
        "vlrTxEmbp": ZERO,
        "vlrFeePagar": ZERO,
        "vlrDescontoAcordo": ZERO,
        "vlrOverRec": ZERO,
        "vlrComisRecebida": ZERO,
        # comissões internas
        "vlrComissaoEmissor": ZERO,
        "vlrComissaoPromotor": ZERO,
        "taxas": [],
    }
    base.update(campos)
    return base


def apartamento(**campos: Any) -> dict[str, Any]:
    """Apartamento de hotel com 1 unidade e 1 diária, valores zerados."""
    base: dict[str, Any] = {
        "idTipoApto": 1,
        "qtde": 1,
        "qtdeDiarias": 1,
        "tipoApartamento": "TIPO EXEMPLO",
        "vlrBalcao": ZERO,
        "vlrDiaria": ZERO,
        "vlrDiariaP": ZERO,
    }
    base.update(campos)
    return base


def _local(sigla: str, cidade: str = "") -> dict[str, Any]:
    return {"sigla": sigla, "aeroporto": "", "cidade": cidade, "pais": "", "fusoHorario": ""}


def trecho(
    segmento: int,
    origem: str,
    destino: str,
    partida: str | None,
    chegada: str | None,
    *,
    origem_cidade: str = "",
    destino_cidade: str = "",
    **campos: Any,
) -> dict[str, Any]:
    """Trecho sem voo nem localizador; `origem` e `destino` são as siglas dos aeroportos.

    `origem_cidade` e `destino_cidade` preenchem `cidade` dos locais (vazia por padrão).
    """
    base: dict[str, Any] = {
        "segmento": segmento,
        "origem": _local(origem, origem_cidade),
        "destino": _local(destino, destino_cidade),
        "dtPartida": partida,
        "dtChegada": chegada,
        "cia": "",
        "voo": "",
        "localizador": "",
        "classe": "",
        "farebase": "",
        "conexao": "",
        "status": "",
    }
    base.update(campos)
    return base


def recebimento(**campos: Any) -> dict[str, Any]:
    """Recebimento faturado do total do cliente da venda padrão."""
    forma = campos.get("forma", 1)
    base: dict[str, Any] = {
        "uniqueid": 1,
        "forma": forma,
        "descricaoForma": FORMAS_RECEBIMENTO.get(forma, ""),
        "valor": Decimal("1050.01"),
        "moedaOriginal": "R$",
        "vlrCambio": UM,
        "dtVencto": VENCIMENTO_PADRAO,
        "ehsinal": False,
        "cartaoRepassadoAoFornecedor": False,
        "idPagante": 1,
        "nomePagante": "CLIENTE EXEMPLO LTDA",
    }
    base.update(campos)
    return base


def pagamento(**campos: Any) -> dict[str, Any]:
    """Pagamento faturado do total do fornecedor da venda padrão."""
    forma = campos.get("forma", 1)
    base: dict[str, Any] = {
        "uniqueid": 1,
        "forma": forma,
        "descricaoForma": FORMAS_PAGAMENTO.get(forma, ""),
        "valor": Decimal("990.00"),
        "moedaOriginal": "R$",
        "vlrCambio": UM,
        "dtVencto": VENCIMENTO_PADRAO,
        "ehsinal": False,
        "idBenificiario": 1,
        "nomeBenificiario": "FORNECEDOR EXEMPLO",
    }
    base.update(campos)
    return base


def venda(**campos: Any) -> dict[str, Any]:
    """Venda FECHADA de Diversos, reserva 90000001, idreserva 1001, um serviço em real que fecha.

    Cliente: 1000.00 + 100.00 + 0.01 - 50.00 = 1050.01. Fornecedor: 900.00 + 90.00 = 990.00.
    Margem 60.01. Um recebimento faturado e um pagamento faturado, ambos quitados nos totais.
    Tem os 72 campos do topo que a AGI sempre manda (`sistemaExterno` às vezes não vem).
    """
    base: dict[str, Any] = {
        "idreserva": 1001,
        "reserva": 90000001,
        "status": "FECHADA",
        "dtemissao": DATA_PADRAO,
        "dtconfirmacao": DATA_PADRAO,
        "dtcriacao": DATA_PADRAO,
        "dtcancelamento": None,
        "dtreabertura": None,
        "dtreativacao": None,
        "dtalteracao": DATA_PADRAO,
        "dtalteracaovinculado": DATA_PADRAO,
        "idproduto": 1,
        "nomeproduto": "PRODUTO EXEMPLO",
        "classificacaoproduto": "Diversos",
        "categoriaproduto": "Nacional",
        "idreservavinculadafee": 0,
        "idCliente": 1,
        "nomecliente": "CLIENTE EXEMPLO LTDA",
        "grupocliente": "",
        "idfornec": 1,
        "nomefornec": "FORNECEDOR EXEMPLO",
        "idfornec2": 1,
        "nomefornec2": "FORNECEDOR EXEMPLO",
        "idemissor": 1,
        "nomeEmissor": "EMISSOR EXEMPLO",
        "idPromotor": 1,
        "nomePromotor": "PROMOTOR EXEMPLO",
        "idAuxiliar": 0,
        "nomeAuxiliar": "",
        "nomeCoordenador": "",
        "idfilial": 1,
        "nomeFilial": "FILIAL EXEMPLO",
        "idCentrocustos": 1,
        "nomeCenctroCustos": "CENTRO DE CUSTOS EXEMPLO",
        "idcCustoCliente": 0,
        "nomeCCustoCliente": "",
        "siglaCCustoCliente": "",
        "idDepSetCli": 0,
        "nomeDeptoSetorCli": "",
        "nomeSolicitante": "",
        "nomeAutorizador": "",
        "projeto": "",
        "atividade": "",
        "midiaOrigem": "",
        "destino": "",
        "intinerario": "",
        "chaveimportacao": "",
        "nomearquivo": "",
        "file": "",
        "tipoVenda": "",
        "tiporegistro": "",
        "situacaoFinanceiroRecebimento": "OK",
        "totalCliente": Decimal("1050.01"),
        "totalFornecedor": Decimal("990.00"),
        "margemLucroBruta": Decimal("60.01"),
        "totalAReceberCliente": Decimal("0.00"),
        "totalRecebidoCliente": Decimal("1050.01"),
        "totalAPagarCliente": Decimal("0.00"),
        "totalPagoCliente": Decimal("0.00"),
        "totalAPagarFornec": Decimal("0.00"),
        "totalPagoFornec": Decimal("990.00"),
        "totalAReceberFornecedor": Decimal("0.00"),
        "totalRecebidoFornec": Decimal("0.00"),
        "taxasAdministrativas": ZERO,
        "taxasAdministrativasRepassadas": ZERO,
        "camposGerenciais": [],
        "detalheItem": [
            servico(
                vlrTarifaTotal=Decimal("1000.00"),
                vlrTaxas=Decimal("100.00"),
                vlrTxServico=Decimal("0.01"),
                vlrDesconto=Decimal("50.00"),
                vlrTarifaTotalp=Decimal("900.00"),
                vlrTaxasP=Decimal("90.00"),
            )
        ],
        "trechos": [],
        "recebimentos": [recebimento()],
        "pagamentos": [pagamento()],
        "reembolsoVinculado": [],
        "financeiroVinculado": {"contasPagar": [], "contasReceber": []},
    }
    base.update(campos)
    return base


def resposta_agi(vendas: list[dict[str, Any]], pagina: int = 1) -> str:
    """Texto JSON de `POST /api/reservas`: `pagina`, `registrosnapagina` e `vendas`."""
    return serializar_cru({"pagina": pagina, "registrosnapagina": len(vendas), "vendas": vendas})


def validar_servico(s: dict[str, Any]) -> ServicoAgi:
    return ServicoAgi.model_validate(s)


def validar_venda(v: dict[str, Any]) -> VendaAgi:
    return VendaAgi.model_validate(v)


def validar_trechos(t: list[dict[str, Any]]) -> list[TrechoAgi]:
    return [TrechoAgi.model_validate(item) for item in t]
