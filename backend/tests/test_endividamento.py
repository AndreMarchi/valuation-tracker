from valuation.endividamento import analisar_endividamento


def test_endividamento_critico():
    """Dívida/EBIT acima de 5x deve gerar alerta crítico."""
    resultado = analisar_endividamento(
        div_liquida=100_000_000_000,
        ebit_12m=15_000_000_000,
        patrim_liq=40_000_000_000,
        score_atual=7.0,
    )
    tipos = [a["tipo"] for a in resultado["alertas"]]
    assert "endividamento_critico" in tipos
    assert resultado["penalizacao"] >= 2.5


def test_endividamento_saudavel():
    """Dívida/EBIT abaixo de 2x não deve gerar alerta."""
    resultado = analisar_endividamento(
        div_liquida=10_000_000_000,
        ebit_12m=20_000_000_000,
        patrim_liq=40_000_000_000,
        score_atual=7.0,
    )
    assert resultado["penalizacao"] == 0.0
    assert resultado["alertas"] == []
    assert resultado["score_ajustado"] == 7.0


def test_score_nao_vai_abaixo_de_zero():
    """Score ajustado nunca deve ser negativo."""
    resultado = analisar_endividamento(
        div_liquida=500_000_000_000,
        ebit_12m=10_000_000_000,
        patrim_liq=5_000_000_000,
        score_atual=2.0,
    )
    assert resultado["score_ajustado"] >= 0.0


def test_alavancagem_alta():
    """Dívida/Patrimônio acima de 2x deve gerar alerta."""
    resultado = analisar_endividamento(
        div_liquida=90_000_000_000,
        ebit_12m=30_000_000_000,
        patrim_liq=40_000_000_000,
        score_atual=7.0,
    )
    tipos = [a["tipo"] for a in resultado["alertas"]]
    assert "alavancagem_alta" in tipos


def test_sem_ebit_nao_quebra():
    """Sem EBIT disponível não deve lançar erro."""
    resultado = analisar_endividamento(
        div_liquida=50_000_000_000,
        ebit_12m=0,
        patrim_liq=40_000_000_000,
        score_atual=7.0,
    )
    assert "score_ajustado" in resultado