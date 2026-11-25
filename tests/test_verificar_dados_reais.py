from pathlib import Path

import pytest

from verificar_dados_reais import main, verificar

# Os literais "reais" são montados por concatenação: o próprio gancho recusaria o número real
# escrito inteiro (idem para o identificador da A3).
NUMERO_REAL = "1567" + "4899"
NUMERO_REAL_B = "1557" + "0001"
IDENTIFICADOR_A3 = "A3" + "TURISMO"


def test_recusa_numero_de_reserva_real(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.py"
    arquivo.write_text("numero = " + NUMERO_REAL + "\n")
    assert verificar([arquivo]) == [f"{arquivo}:1: número de reserva real"]


def test_recusa_a_faixa_155_e_156(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.py"
    arquivo.write_text(NUMERO_REAL_B + "\n" + NUMERO_REAL + "\n")
    assert verificar([arquivo]) == [
        f"{arquivo}:1: número de reserva real",
        f"{arquivo}:2: número de reserva real",
    ]


def test_recusa_identificador_da_a3_na_url(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.md"
    arquivo.write_text("https://x.invalid/" + IDENTIFICADOR_A3 + "/api\n")
    assert verificar([arquivo]) == [f"{arquivo}:1: identificador da A3"]


def test_aceita_numero_inventado(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.py"
    arquivo.write_text("numero = 90000001\n")
    assert verificar([arquivo]) == []


@pytest.mark.parametrize(
    "texto",
    [
        "RE_" + NUMERO_REAL,
        NUMERO_REAL + "_tela",
        "v" + NUMERO_REAL + ".png",
        "id=" + NUMERO_REAL + ";",
    ],
)
def test_recusa_numero_colado_a_letras_ou_sublinhado(tmp_path: Path, texto: str) -> None:
    # o `\b` antigo não separava dígito de `_`/letra e deixava passar estes casos
    arquivo = tmp_path / "x.py"
    arquivo.write_text(texto + "\n")
    assert verificar([arquivo]) == [f"{arquivo}:1: número de reserva real"]


@pytest.mark.parametrize("texto", ["9" + NUMERO_REAL, NUMERO_REAL + "9", "9" + NUMERO_REAL + "9"])
def test_numero_maior_que_contem_o_padrao_nao_e_reserva(tmp_path: Path, texto: str) -> None:
    arquivo = tmp_path / "x.py"
    arquivo.write_text(texto + "\n")
    assert verificar([arquivo]) == []


def test_arquivo_latin1_e_verificado(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.txt"
    arquivo.write_bytes("reserva ação ".encode("latin-1") + NUMERO_REAL.encode() + b"\n")
    assert verificar([arquivo]) == [f"{arquivo}:1: número de reserva real"]


def test_numero_real_no_caminho(tmp_path: Path) -> None:
    arquivo = tmp_path / ("v" + NUMERO_REAL + ".png")
    arquivo.write_bytes(b"conteudo limpo\n")
    assert verificar([arquivo]) == [f"{arquivo}: número de reserva real (no caminho)"]


def test_identificador_da_a3_no_caminho(tmp_path: Path) -> None:
    arquivo = tmp_path / (IDENTIFICADOR_A3.lower() + ".txt")
    arquivo.write_text("limpo\n")
    assert verificar([arquivo]) == [f"{arquivo}: identificador da A3 (no caminho)"]


def test_binario_com_nul_checa_so_o_caminho(tmp_path: Path) -> None:
    # sem o número no caminho, o conteúdo binário não é varrido (evita falso positivo)
    binario = tmp_path / "imagem.png"
    binario.write_bytes(b"\x89PNG\x00\x00" + NUMERO_REAL.encode() + b"\x00")
    assert verificar([binario]) == []
    # com o número no caminho, o caminho continua sendo checado
    nomeado = tmp_path / ("tela_" + NUMERO_REAL + ".png")
    nomeado.write_bytes(b"\x89PNG\x00\x00")
    assert verificar([nomeado]) == [f"{nomeado}: número de reserva real (no caminho)"]


def test_arquivo_ilegivel_vira_problema(tmp_path: Path) -> None:
    inexistente = tmp_path / "nao_existe.py"
    assert verificar([inexistente]) == [
        f"{inexistente}: arquivo não pôde ser lido (FileNotFoundError)"
    ]


def test_main_devolve_1_com_problema_e_0_sem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ruim = tmp_path / "ruim.py"
    ruim.write_text("n = " + NUMERO_REAL + "\n")
    bom = tmp_path / "bom.py"
    bom.write_text("n = 90000001\n")
    assert main([str(ruim)]) == 1
    assert "número de reserva real" in capsys.readouterr().err
    assert main([str(bom)]) == 0
    assert main([]) == 0
    assert main([str(tmp_path / "nao_existe.py")]) == 1
