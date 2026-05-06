from valuation.multiplos import calcular_multiplos


def test_pl_descontado():
    """P/L atual bem abaixo da média histórica."""
    resultado = calcular_multiplos(
        pl_atual=6.0, pvp_atual=1.5,
        pl_medio_historico=10.0, pvp_medio_historico=1.8,
        preco_atual=30.0
    )
    assert resultado["pl"]["classificacao"] == "Descontada"
    assert resultado["pl"]["desconto"] == 40.0


def test_pvp_descontado():
    """P/VP atual bem abaixo da média histórica."""
    resultado = calcular_multiplos(
        pl_atual=10.0, pvp_atual=1.0,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=30.0
    )
    assert resultado["pvp"]["classificacao"] == "Descontada"
    assert resultado["pvp"]["desconto"] == 50.0


def test_pl_caro():
    """P/L atual acima da média histórica."""
    resultado = calcular_multiplos(
        pl_atual=15.0, pvp_atual=2.0,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=50.0
    )
    assert resultado["pl"]["classificacao"] == "Cara"
    assert resultado["pl"]["desconto"] < 0


def test_pl_neutro():
    """P/L atual próximo da média histórica."""
    resultado = calcular_multiplos(
        pl_atual=9.0, pvp_atual=2.0,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=50.0
    )
    assert resultado["pl"]["classificacao"] == "Neutra"


def test_pl_negativo():
    """P/L negativo — empresa com prejuízo."""
    resultado = calcular_multiplos(
        pl_atual=-5.0, pvp_atual=1.5,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=20.0
    )
    assert resultado["pl"]["classificacao"] == "Não aplicável"
    assert resultado["pl"]["desconto"] is None