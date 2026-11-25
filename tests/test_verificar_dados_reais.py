from pathlib import Path

from verificar_dados_reais import verificar


def test_recusa_numero_de_reserva_real(tmp_path: Path) -> None:
    # o literal é montado por concatenação: o próprio gancho recusaria o número real escrito inteiro
    # (idem para o identificador da A3)
    arquivo = tmp_path / "x.py"
    arquivo.write_text("numero = " + "1567" + "4899\n")
    assert verificar([arquivo]) == [f"{arquivo}:1: número de reserva real"]


def test_recusa_identificador_da_a3_na_url(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.md"
    arquivo.write_text("https://x.invalid/" + "A3TUR" + "ISMO/api\n")
    assert verificar([arquivo]) == [f"{arquivo}:1: identificador da A3"]


def test_aceita_numero_inventado(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.py"
    arquivo.write_text("numero = 90000001\n")
    assert verificar([arquivo]) == []
