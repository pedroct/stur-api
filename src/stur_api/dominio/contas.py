"""Contas por serviço (cliente, fornecedor, margem) e verificação dos totais da venda (PRD 8.3).

Código puro, sem entrada nem saída. Campo ausente (`None`) conta como zero. Os totais ficam
sem arredondar para comparar; o arredondamento para 2 casas (`ROUND_HALF_UP`) é do contrato.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from stur_api.agi.modelos import ServicoAgi, VendaAgi
from stur_api.config import Configuracao

ZERO = Decimal("0")
UM = Decimal("1")
CEM = Decimal("100")
DUAS_CASAS = Decimal("0.01")
SIGLAS_REAL = frozenset({"R$", "BRL"})

Efeito = Literal["soma", "reduz"]

# (campo da AGI, efeito), na ordem em que a conta aparece. A tarifa vem à parte, multiplicada
# pelo câmbio.
_TERMOS_CLIENTE: tuple[tuple[str, Efeito], ...] = (
    ("vlrTaxas", "soma"),
    ("vlrTxExt", "soma"),
    ("vlrTxServico", "soma"),
    ("vlrTxEmb", "soma"),
    ("vlrTxDU", "soma"),
    ("vlrDesconto", "reduz"),
    ("vlrTxDURepassada", "reduz"),
    ("vlrOverRep", "reduz"),
    ("vlrComisRepassada", "reduz"),
)
_TERMOS_FORNECEDOR: tuple[tuple[str, Efeito], ...] = (
    ("vlrTaxasP", "soma"),
    ("vlrTxExtP", "soma"),
    ("vlrTxEmbp", "soma"),
    ("vlrFeePagar", "soma"),
    ("vlrDescontoAcordo", "reduz"),
    ("vlrOverRec", "reduz"),
    ("vlrComisRecebida", "reduz"),
)


@dataclass(frozen=True)
class TermoConta:
    campo: str  # nome do campo na AGI
    valor: Decimal
    efeito: Efeito


@dataclass(frozen=True)
class Conversao:
    sigla: str
    tarifa_origem: Decimal
    cambio: Decimal
    data_cambio: str | None


@dataclass(frozen=True)
class ContaLado:
    termos: list[TermoConta]
    zerados: list[str]
    total: Decimal
    conversao: Conversao | None
    sigla_com_cambio_1: str | None


@dataclass(frozen=True)
class ContaServico:
    indice: int
    cliente: ContaLado
    fornecedor: ContaLado
    margem: Decimal
    percentual_lucro: Decimal | None
    comissoes_nao_apuradas: bool


@dataclass(frozen=True)
class ContaVerificada:
    conta: Literal["cliente", "fornecedor", "margem"]
    calculado: Decimal
    api: Decimal
    diferenca: Decimal
    fecha: bool


@dataclass(frozen=True)
class Verificacao:
    contas: list[ContaVerificada]
    tolerancia: Decimal
    fecha: bool


def _valor(servico: ServicoAgi, campo: str) -> Decimal:
    valor: Decimal | None = getattr(servico, campo)
    return ZERO if valor is None else valor


def _conta_do_lado(
    servico: ServicoAgi,
    campo_tarifa: str,
    campo_cambio: str,
    campo_sigla: str,
    campo_data_cambio: str,
    outros: tuple[tuple[str, Efeito], ...],
) -> ContaLado:
    tarifa = _valor(servico, campo_tarifa)
    cambio = _valor(servico, campo_cambio)
    sigla: str | None = getattr(servico, campo_sigla)
    conversao: Conversao | None = None
    sigla_com_cambio_1: str | None = None
    if sigla is not None and sigla.strip().upper() not in SIGLAS_REAL | {""}:
        if cambio == UM:
            sigla_com_cambio_1 = sigla
        else:
            conversao = Conversao(sigla, tarifa, cambio, getattr(servico, campo_data_cambio))

    # a tarifa nunca sai dos termos, mesmo zerada
    termos = [TermoConta(campo_tarifa, tarifa * cambio, "soma")]
    zerados: list[str] = []
    for campo, efeito in outros:
        valor = _valor(servico, campo)
        if valor == ZERO:
            zerados.append(campo)
        else:
            termos.append(TermoConta(campo, valor, efeito))
    total = sum(
        (t.valor if t.efeito == "soma" else -t.valor for t in termos),
        start=ZERO,
    )
    return ContaLado(termos, zerados, total, conversao, sigla_com_cambio_1)


def percentual_lucro(margem: Decimal, total_cliente: Decimal) -> Decimal | None:
    """Margem sobre o total do cliente, em %, com 2 casas. `None` com total zero (não se aplica)."""
    if total_cliente == ZERO:
        return None
    return (margem / total_cliente * CEM).quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)


def conta_do_servico(servico: ServicoAgi, indice: int, situacao: str) -> ContaServico:
    """Contas de um serviço. `situacao` é o `status` da AGI da venda (`FECHADA`, `CONFIRMADA`)."""
    cliente = _conta_do_lado(
        servico,
        "vlrTarifaTotal",
        "vlrCambio",
        "siglaMoedaTarifa",
        "dtCambio",
        _TERMOS_CLIENTE,
    )
    fornecedor = _conta_do_lado(
        servico,
        "vlrTarifaTotalp",
        "vlrCambiop",
        "siglaMoedaTarifap",
        "dtCambiop",
        _TERMOS_FORNECEDOR,
    )
    margem = cliente.total - fornecedor.total
    comissoes_zeradas = (
        _valor(servico, "vlrComissaoEmissor") == ZERO
        and _valor(servico, "vlrComissaoPromotor") == ZERO
    )
    return ContaServico(
        indice=indice,
        cliente=cliente,
        fornecedor=fornecedor,
        margem=margem,
        percentual_lucro=percentual_lucro(margem, cliente.total),
        comissoes_nao_apuradas=comissoes_zeradas and situacao.strip().upper() != "FECHADA",
    )


def verificar_totais(
    venda: VendaAgi, contas: list[ContaServico], config: Configuracao
) -> Verificacao:
    """Compara a soma dos serviços com os totais da venda (cliente, fornecedor e margem)."""
    convertidos = sum(
        1 for c in contas if c.cliente.conversao is not None or c.fornecedor.conversao is not None
    )
    tolerancia = config.tolerancia_real
    if convertidos:
        tolerancia = max(tolerancia, config.tolerancia_moeda_por_servico * convertidos)

    total_cliente = sum((c.cliente.total for c in contas), start=ZERO)
    total_fornecedor = sum((c.fornecedor.total for c in contas), start=ZERO)
    pares: tuple[
        tuple[Literal["cliente", "fornecedor", "margem"], Decimal, Decimal | None], ...
    ] = (
        ("cliente", total_cliente, venda.totalCliente),
        ("fornecedor", total_fornecedor, venda.totalFornecedor),
        ("margem", total_cliente - total_fornecedor, venda.margemLucroBruta),
    )
    verificadas = []
    for conta, calculado, api_ou_none in pares:
        api = ZERO if api_ou_none is None else api_ou_none
        diferenca = calculado - api
        verificadas.append(
            ContaVerificada(conta, calculado, api, diferenca, abs(diferenca) <= tolerancia)
        )
    return Verificacao(verificadas, tolerancia, all(v.fecha for v in verificadas))
