from valuation.ev_ebitda import calcular_ev_ebitda


def test_ev_ebitda_descontado():
    """EV/EBITDA abaixo das médias de mercado deve ser classificado como descontado."""
    resultado = calcular_ev_ebitda(
        ev_ebitda_atual=3.0,
        ev_ebitda_historico=6.0,  # Parâmetro adicionado
        ev_ebitda_setor=5.0,      # Parâmetro adicionado
        ebit_12m=194_000_000_000,
        num_acoes=13_000_000_000,
        div_liquida=324_000_000_000,
    )
    assert resultado["classificacao"] == "Descontada"

def test_ev_ebitda_caro():
    """EV/EBITDA acima das médias deve ser classificado como caro."""
    resultado = calcular_ev_ebitda(
        ev_ebitda_atual=12.0,
        ev_ebitda_historico=6.0,  # Parâmetro adicionado
        ev_ebitda_setor=5.0,      # Parâmetro adicionado
        ebit_12m=10_000_000_000,
        num_acoes=1_000_000_000,
        div_liquida=5_000_000_000,
    )
    assert resultado["classificacao"] == "Cara"

def test_ev_ebitda_dados_invalidos():
    """Dados zerados devem retornar não aplicável."""
    resultado = calcular_ev_ebitda(
        ev_ebitda_atual=0, # Ajustado para 0 para testar o cenário inválido
        ev_ebitda_historico=6.0,
        ev_ebitda_setor=5.0,
        ebit_12m=0,
        num_acoes=0,
        div_liquida=0,
    )
    assert resultado["classificacao"] == "Não aplicável"


def test_ev_ebitda_retorna_preco_justo():
    """Deve retornar preço justo quando dados válidos."""
    resultado = calcular_ev_ebitda(
        ev_ebitda_atual=3.0,
        ev_ebitda_historico=6.0,
        ev_ebitda_setor=5.0,
        ebit_12m=194_000_000_000,
        num_acoes=13_000_000_000,
        div_liquida=324_000_000_000,
    )
    assert resultado["preco_justo"] is not None
    assert resultado["preco_justo"] > 0