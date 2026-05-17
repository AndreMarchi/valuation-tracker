from valuation.ev_ebitda import calcular_ev_ebitda


def test_ev_ebitda_descontado():
    """EV/EBITDA abaixo da média setorial deve ser descontado."""
    resultado = calcular_ev_ebitda(
        ev_ebitda_atual=3.0,
        setor="Petróleo, Gás e Biocombustíveis",
        ebit_12m=194_000_000_000,
        num_acoes=13_000_000_000,
        div_liquida=324_000_000_000,
    )
    assert resultado["classificacao"] == "Descontada"


def test_ev_ebitda_caro():
    """EV/EBITDA acima da média setorial deve ser caro."""
    resultado = calcular_ev_ebitda(
        ev_ebitda_atual=20.0,
        setor="Alimentos",
        ebit_12m=10_000_000_000,
        num_acoes=1_000_000_000,
        div_liquida=5_000_000_000,
    )
    assert resultado["classificacao"] == "Cara"


def test_ev_ebitda_dados_invalidos():
    """Dados zerados devem retornar não aplicável."""
    resultado = calcular_ev_ebitda(
        ev_ebitda_atual=0,
        setor="Varejo",
        ebit_12m=0,
        num_acoes=0,
        div_liquida=0,
    )
    assert resultado["classificacao"] == "Não aplicável"


def test_ev_ebitda_retorna_preco_justo():
    """Deve retornar preço justo quando dados válidos."""
    resultado = calcular_ev_ebitda(
        ev_ebitda_atual=4.0,
        setor="Mineração",
        ebit_12m=50_000_000_000,
        num_acoes=5_000_000_000,
        div_liquida=20_000_000_000,
    )
    assert resultado["preco_justo"] is not None
    assert resultado["preco_justo"] > 0