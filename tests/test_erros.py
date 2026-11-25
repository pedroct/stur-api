import pytest

from stur_api.erros import (
    ApiSturAcessoRecusado,
    ApiSturRespostaInvalida,
    ApiSturSemResposta,
    ConsultaInvalida,
    ErroAplicacao,
    ErroInterno,
    VendaNaoEncontrada,
)


@pytest.mark.parametrize(
    ("erro", "status_http", "codigo"),
    [
        (ApiSturSemResposta(30), 504, "api_stur_sem_resposta"),
        (ApiSturAcessoRecusado(), 502, "api_stur_acesso_recusado"),
        (ApiSturRespostaInvalida(), 502, "api_stur_resposta_invalida"),
        (VendaNaoEncontrada(), 404, "venda_nao_encontrada"),
        (ErroInterno(), 500, "erro_interno"),
    ],
)
def test_cada_erro_tem_status_e_codigo(erro: ErroAplicacao, status_http: int, codigo: str) -> None:
    assert isinstance(erro, ErroAplicacao)
    assert erro.status_http == status_http
    assert erro.codigo == codigo
    assert erro.mensagem


def test_sem_resposta_diz_o_tempo_limite() -> None:
    assert "30 segundos" in ApiSturSemResposta(30).mensagem
    assert "45 segundos" in ApiSturSemResposta(45).mensagem


def test_mensagens_da_tabela() -> None:
    assert ApiSturAcessoRecusado().mensagem == (
        "A API do Stur recusou o acesso desta aplicação. "
        "O acesso pode ter sido encerrado. Avise o Pedro."
    )
    assert ApiSturRespostaInvalida().mensagem == (
        "A API do Stur respondeu num formato que esta aplicação não reconhece."
    )
    assert VendaNaoEncontrada().mensagem == (
        "Nenhuma venda com esse número de reserva e esse id interno."
    )
    assert ErroInterno().mensagem == "Algo deu errado nesta aplicação, não na API do Stur."


def test_resposta_invalida_leva_o_caminho_do_campo_no_detalhe() -> None:
    erro = ApiSturRespostaInvalida(detalhe={"campo": "servicos[0].vlrtarifa"})
    assert erro.detalhe == {"campo": "servicos[0].vlrtarifa"}
    assert ApiSturRespostaInvalida().detalhe is None


def test_consulta_invalida_leva_codigo_mensagem_e_campo() -> None:
    erro = ConsultaInvalida("periodo_longo", "O período passa de 31 dias.", "ate")
    assert erro.status_http == 422
    assert erro.codigo == "periodo_longo"
    assert erro.mensagem == "O período passa de 31 dias."
    assert erro.campo == "ate"
