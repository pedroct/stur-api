from stur_api.dominio.textos import normalizar


def test_normalizar_tira_acento_caixa_e_espacos() -> None:
    assert normalizar("  Aéreo  ") == "AEREO"
    assert normalizar("Locação") == "LOCACAO"
    assert normalizar("taxa   fee") == "TAXA FEE"


def test_normalizar_iguala_a_grafia_da_agi_e_a_do_plano() -> None:
    assert normalizar("Rodoviario") == normalizar("Rodoviário")
