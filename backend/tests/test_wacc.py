import pytest
from valuation.wacc import calcular_wacc

def test_wacc_empresa_sem_divida():
    """Se a empresa não tem dívidas, o WACC deve ser igual à taxa CAPM."""
    dados_mock = {
        "preco_atual": 10.00,
        "num_acoes": 1000000,
        "div_liquida": 0,
        "selic": 0.145
    }
    taxa_capm = 0.16 # 16%
    
    wacc = calcular_wacc(dados_mock, taxa_capm)
    
    # Com 0 de dívida, o peso do Equity é 100%, então WACC = CAPM
    assert wacc == pytest.approx(0.16)

def test_wacc_empresa_com_divida_equilibra_taxas():
    """Valida o cálculo ponderado quando há equilíbrio entre dívida e capital próprio."""
    dados_mock = {
        "preco_atual": 20.00,
        "num_acoes": 500000,  # Equity = 10.000.000
        "div_liquida": 10000000, # Dívida = 10.000.000 (Peso 50% / 50%)
        "selic": 0.145
    }
    taxa_capm = 0.16  # 16%
    
    # Racional do cálculo interno:
    # Equity = 10M, Dívida = 10M -> Total = 20M (Peso = 0.5 para cada)
    # Kd = 14.5% + 3% = 17.5% -> Kd_apos_imposto = 17.5% * (1 - 0.34) = 11.55%
    # WACC esperado = (0.5 * 16%) + (0.5 * 11.55%) = 8% + 5.775% = 13.775%
    
    wacc = calcular_wacc(dados_mock, taxa_capm)
    assert wacc == pytest.approx(0.13775)

def test_wacc_limite_minimo_seguranca():
    """Garante que o benefício fiscal da dívida não jogue o WACC abaixo do piso de 8%."""
    dados_mock = {
        "preco_atual": 1.00,
        "num_acoes": 100000,  # Equity minúsculo = 100.000
        "div_liquida": 50000000, # Dívida gigante = 50.000.000 (Peso da dívida esmagador)
        "selic": 0.05  # Selic simulada muito baixa
    }
    taxa_capm = 0.08
    
    wacc = calcular_wacc(dados_mock, taxa_capm)
    
    # O cálculo bruto daria muito baixo, mas o filtro 'max(0.08, ...)' deve travar em 8%
    assert wacc == 0.08

def test_wacc_fallback_dados_zerados():
    """Caso o total de ativos/market cap seja zero por falha de dados, deve retornar o fallback de 12%."""
    dados_mock = {
        "preco_atual": 0.0,
        "num_acoes": 0,
        "div_liquida": 0,
        "selic": 0.145
    }
    
    wacc = calcular_wacc(dados_mock, taxa_capm=0.16)
    assert wacc == 0.12