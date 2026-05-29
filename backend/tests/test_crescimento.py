from valuation.crescimento import (
    detectar_fase_crescimento,
    calcular_peg_ratio,
    calcular_ev_receita,
    calcular_rule_of_40,
    calcular_dcf_duas_fases,
)


def test_detectar_crescimento_alto():
    assert detectar_fase_crescimento(0.20) == "alto"


def test_detectar_crescimento_medio():
    assert detectar_fase_crescimento(0.10) == "medio"


def test_detectar_crescimento_maduro():
    assert detectar_fase_crescimento(0.03) == "maduro"


def test_peg_descontado():
    """P/L 10x com crescimento 20% → PEG 0.5 → descontada."""
    resultado = calcular_peg_ratio(pl=10.0, crescimento_lucro=0.20)
    assert resultado["peg"] == 0.5
    assert resultado["classificacao"] == "Descontada"


def test_peg_caro():
    """P/L 50x com crescimento 10% → PEG 5.0 → cara."""
    resultado = calcular_peg_ratio(pl=50.0, crescimento_lucro=0.10)
    assert resultado["classificacao"] == "Cara"


def test_peg_nao_aplicavel():
    """Crescimento negativo → não aplicável."""
    resultado = calcular_peg_ratio(pl=10.0, crescimento_lucro=-0.05)
    assert resultado["classificacao"] == "Não aplicável"


def test_rule_of_40_excelente():
    """Crescimento 40% + Margem 30% = 70% → excelente."""
    resultado = calcular_rule_of_40(0.40, 0.30)
    assert resultado["rule_of_40"] == 70.0
    assert resultado["classificacao"] == "Excelente"


def test_rule_of_40_saudavel():
    """Crescimento 20% + Margem 25% = 45% → saudável."""
    resultado = calcular_rule_of_40(0.20, 0.25)
    assert resultado["classificacao"] == "Saudável"


def test_rule_of_40_preocupante():
    """Crescimento 5% + Margem 5% = 10% → preocupante."""
    resultado = calcular_rule_of_40(0.05, 0.05)
    assert resultado["classificacao"] == "Preocupante"


def test_dcf_duas_fases_retorna_campos():
    resultado = calcular_dcf_duas_fases(
        lucro_por_acao=2.29,
        crescimento_fase1=0.20,
        anos_fase1=5,
        crescimento_fase2=0.04,
        taxa_desconto=0.14,
        preco_atual=72.53,
    )
    assert "valor_intrinseco" in resultado
    assert "cenarios" in resultado
    assert resultado["cenarios"]["otimista"] > resultado["cenarios"]["base"]
    assert resultado["cenarios"]["pessimista"] < resultado["cenarios"]["base"]


def test_dcf_duas_fases_lpa_negativo():
    resultado = calcular_dcf_duas_fases(
        lucro_por_acao=-1.0,
        crescimento_fase1=0.20,
        anos_fase1=5,
        crescimento_fase2=0.04,
        taxa_desconto=0.14,
        preco_atual=50.0,
    )
    assert resultado["classificacao"] == "Não aplicável"


def test_ev_receita_descontado():
    resultado = calcular_ev_receita(
        psr_atual=0.8,
        setor="Material de Transporte",
        receita_12m=43_000_000_000,
        num_acoes=740_000_000,
        div_liquida=5_000_000_000,
        valor_mercado=50_000_000_000,
    )
    assert resultado["classificacao"] == "Descontada"