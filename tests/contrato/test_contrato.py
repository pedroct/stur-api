from dataclasses import fields
from decimal import Decimal
from types import NoneType
from typing import get_args, get_type_hints

import pytest
from pydantic import BaseModel
from pydantic.alias_generators import to_camel

from stur_api.contrato import calculos, venda
from stur_api.contrato.comum import Contrato, DecimalTexto, decimais_em_texto
from stur_api.dominio import (
    contas,
    estado_servico,
    itinerario,
    lancamentos,
    resultado,
    servico,
    vendas,
)


class _Exemplo(Contrato):
    total_cliente: DecimalTexto
    percentual_lucro: DecimalTexto | None


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        (Decimal("1050.01"), "1050.01"),
        (Decimal("0"), "0"),
        (Decimal("1E+5"), "100000"),  # sem notação científica
        (Decimal("-0.000000001"), "-0.000000001"),
    ],
)
def test_decimal_sai_como_texto_sem_expoente(valor: Decimal, texto: str) -> None:
    json = _Exemplo(total_cliente=valor, percentual_lucro=None).model_dump(mode="json")
    assert json == {"totalCliente": texto, "percentualLucro": None}


def test_campos_em_camel_case_e_aceita_o_nome_do_python() -> None:
    por_nome = _Exemplo(total_cliente=Decimal("1"), percentual_lucro=Decimal("2"))
    por_alias = _Exemplo.model_validate({"totalCliente": "1", "percentualLucro": "2"})
    assert por_nome == por_alias
    assert por_nome.model_dump() == {"totalCliente": Decimal("1"), "percentualLucro": Decimal("2")}


@pytest.mark.parametrize(
    ("dominio", "contrato"),
    [
        (vendas.ResumoVenda, calculos.ResumoVenda),
        (resultado.ResumoResultado, calculos.ResumoResultado),
        (resultado.ResumoIncentivos, calculos.ResumoIncentivos),
        (vendas.TotaisReserva, calculos.TotaisReserva),
        (contas.TermoConta, calculos.TermoConta),
        (contas.Conversao, calculos.Conversao),
        (contas.ContaLado, calculos.ContaLado),
        (contas.ContaServico, calculos.ContaServico),
        (contas.ContaVerificada, calculos.ContaVerificada),
        (contas.Verificacao, calculos.Verificacao),
        (lancamentos.LancamentoCalculado, calculos.LancamentoCalculado),
        (itinerario.Espera, calculos.Espera),
        (itinerario.Trajeto, calculos.Trajeto),
        (itinerario.Estadia, calculos.Estadia),
        (itinerario.Itinerario, calculos.Itinerario),
        (estado_servico.EstadoServico, calculos.EstadoServico),
        (lancamentos.Documento, calculos.Documento),
        (servico.ResumoServico, venda.ResumoServico),
    ],
)
def test_contrato_tem_os_campos_do_dominio(dominio: type, contrato: type[BaseModel]) -> None:
    nomes = [f.name for f in fields(dominio)]
    assert list(contrato.model_fields) == nomes
    assert [contrato.model_fields[n].alias for n in nomes] == [to_camel(n) for n in nomes]


# O domínio pode ter `None` onde o contrato não tem: só estes campos, e por quê.
# `validar_venda` recusa venda sem `reserva`/`idreserva` antes de qualquer `resumir`.
_CONTRATO_MAIS_ESTRITO = {("ResumoVenda", "numero"), ("ResumoVenda", "idreserva")}


@pytest.mark.parametrize(
    ("dominio", "contrato"),
    [
        (vendas.ResumoVenda, calculos.ResumoVenda),
        (resultado.ResumoResultado, calculos.ResumoResultado),
        (resultado.ResumoIncentivos, calculos.ResumoIncentivos),
        (vendas.TotaisReserva, calculos.TotaisReserva),
        (contas.TermoConta, calculos.TermoConta),
        (contas.Conversao, calculos.Conversao),
        (contas.ContaLado, calculos.ContaLado),
        (contas.ContaServico, calculos.ContaServico),
        (contas.ContaVerificada, calculos.ContaVerificada),
        (contas.Verificacao, calculos.Verificacao),
        (lancamentos.LancamentoCalculado, calculos.LancamentoCalculado),
        (itinerario.Espera, calculos.Espera),
        (itinerario.Trajeto, calculos.Trajeto),
        (itinerario.Estadia, calculos.Estadia),
        (itinerario.Itinerario, calculos.Itinerario),
        (estado_servico.EstadoServico, calculos.EstadoServico),
        (lancamentos.Documento, calculos.Documento),
        (servico.ResumoServico, venda.ResumoServico),
    ],
)
def test_contrato_nao_muda_a_nulidade_do_dominio(dominio: type, contrato: type[BaseModel]) -> None:
    dicas = get_type_hints(dominio)
    for nome in dicas:
        no_dominio = NoneType in get_args(dicas[nome])
        no_contrato = NoneType in get_args(contrato.model_fields[nome].annotation)
        if (dominio.__name__, nome) in _CONTRATO_MAIS_ESTRITO:
            assert no_dominio
            assert not no_contrato
        else:
            assert no_dominio == no_contrato, f"{dominio.__name__}.{nome}"


def test_resumo_venda_do_contrato_exige_numero_e_idreserva() -> None:
    assert calculos.ResumoVenda.model_fields["numero"].annotation is int
    assert calculos.ResumoVenda.model_fields["idreserva"].annotation is int


def test_decimais_em_texto_em_qualquer_nivel() -> None:
    valor = {"a": Decimal("0.000000000"), "b": [{"c": Decimal("1E+5")}, "x", 1, None, True]}
    assert decimais_em_texto(valor) == {
        "a": "0.000000000",
        "b": [{"c": "100000"}, "x", 1, None, True],
    }
