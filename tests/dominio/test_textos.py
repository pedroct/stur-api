from stur_api.dominio.textos import contem, normalizar


def test_normalizar_tira_acento_caixa_e_espacos() -> None:
    assert normalizar("  Aéreo  ") == "AEREO"
    assert normalizar("Locação") == "LOCACAO"
    assert normalizar("taxa   fee") == "TAXA FEE"


def test_normalizar_iguala_a_grafia_da_agi_e_a_do_plano() -> None:
    assert normalizar("Rodoviario") == normalizar("Rodoviário")


def test_contem_ignora_acento_e_caixa() -> None:
    assert contem("EXPRESSO AÇAÍ LTDA", "acai") and not contem(None, "x")


def test_contem_busca_em_qualquer_parte_e_colapsa_espacos() -> None:
    assert contem("Hotel   Praia Grande", "praia grande")
    assert not contem("Hotel Praia Grande", "serra")
