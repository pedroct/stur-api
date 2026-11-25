from typing import Any


class ErroAplicacao(Exception):
    """Erro que vira resposta `{"codigo", "mensagem", "detalhe"}` ao cliente."""

    status_http: int = 500
    codigo: str = "erro_interno"
    mensagem: str = "Algo deu errado nesta aplicação, não na API do Stur."

    def __init__(
        self,
        codigo: str | None = None,
        mensagem: str | None = None,
        detalhe: Any = None,
    ) -> None:
        if codigo is not None:
            self.codigo = codigo
        if mensagem is not None:
            self.mensagem = mensagem
        self.detalhe = detalhe
        super().__init__(self.mensagem)


class ApiSturSemResposta(ErroAplicacao):
    status_http = 504
    codigo = "api_stur_sem_resposta"

    def __init__(self, tempo_limite_s: int, detalhe: Any = None) -> None:
        super().__init__(
            mensagem=(
                f"A API do Stur não respondeu em {tempo_limite_s} segundos. "
                "Tente de novo em alguns minutos."
            ),
            detalhe=detalhe,
        )


class ApiSturAcessoRecusado(ErroAplicacao):
    status_http = 502
    codigo = "api_stur_acesso_recusado"
    mensagem = (
        "A API do Stur recusou o acesso desta aplicação. "
        "O acesso pode ter sido encerrado. Avise o Pedro."
    )

    def __init__(self, detalhe: Any = None) -> None:
        super().__init__(detalhe=detalhe)


class ApiSturRespostaInvalida(ErroAplicacao):
    status_http = 502
    codigo = "api_stur_resposta_invalida"
    mensagem = "A API do Stur respondeu num formato que esta aplicação não reconhece."

    def __init__(self, detalhe: Any = None) -> None:
        super().__init__(detalhe=detalhe)


class ConsultaInvalida(ErroAplicacao):
    status_http = 422

    def __init__(self, codigo: str, mensagem: str, campo: str, detalhe: Any = None) -> None:
        super().__init__(codigo=codigo, mensagem=mensagem, detalhe=detalhe)
        self.campo = campo


class VendaNaoEncontrada(ErroAplicacao):
    status_http = 404
    codigo = "venda_nao_encontrada"
    mensagem = "Nenhuma venda com esse número de reserva e esse id interno."

    def __init__(self, detalhe: Any = None) -> None:
        super().__init__(detalhe=detalhe)


class ErroInterno(ErroAplicacao):
    status_http = 500
    codigo = "erro_interno"
    mensagem = "Algo deu errado nesta aplicação, não na API do Stur."

    def __init__(self, detalhe: Any = None) -> None:
        super().__init__(detalhe=detalhe)
