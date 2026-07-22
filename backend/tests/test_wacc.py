import pytest
from valuation.wacc import calcular_wacc, calcular_spread_cambial, PREMIO_RISCO_CAMBIAL_PLENO

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


# ─── spread cambial no Kd (dívida em moeda estrangeira) ────────────────────

def test_spread_cambial_zero_sem_dado():
    """None (dado indisponível) não deve penalizar — spread 0."""
    assert calcular_spread_cambial(None) == 0.0


def test_spread_cambial_zero_quando_pct_zero():
    """0% de dívida em moeda estrangeira -> spread 0."""
    assert calcular_spread_cambial(0.0) == 0.0


def test_spread_cambial_proporcional_ao_percentual():
    """Spread cresce linearmente com a fração da dívida exposta."""
    assert calcular_spread_cambial(100.0) == pytest.approx(PREMIO_RISCO_CAMBIAL_PLENO)
    assert calcular_spread_cambial(50.0) == pytest.approx(PREMIO_RISCO_CAMBIAL_PLENO / 2)
    assert calcular_spread_cambial(90.0) == pytest.approx(PREMIO_RISCO_CAMBIAL_PLENO * 0.9)


def test_wacc_sem_dado_cambial_e_identico_ao_comportamento_anterior():
    """calcular_wacc() sem o novo parâmetro (ou com None) deve dar exatamente
    o mesmo resultado de antes desta mudança — não pode quebrar quem já
    chama a função sem o argumento novo."""
    dados_mock = {
        "preco_atual": 20.00,
        "num_acoes": 500000,
        "div_liquida": 10000000,
        "selic": 0.145,
    }
    taxa_capm = 0.16

    wacc_sem_argumento = calcular_wacc(dados_mock, taxa_capm)
    wacc_com_none_explicito = calcular_wacc(dados_mock, taxa_capm, pct_divida_moeda_estrangeira=None)

    assert wacc_sem_argumento == pytest.approx(0.13775)  # mesmo valor do teste de equilíbrio acima
    assert wacc_com_none_explicito == pytest.approx(wacc_sem_argumento)


def test_wacc_com_divida_cambial_alta_fica_maior_que_sem_cambio():
    """Dívida majoritariamente em moeda estrangeira -> Kd maior -> WACC maior
    que o mesmo cenário sem exposição cambial, com valores conferíveis à mão."""
    dados_mock = {
        "preco_atual": 20.00,
        "num_acoes": 500000,  # Equity = 10.000.000
        "div_liquida": 10000000,  # Dívida = 10.000.000 (peso 50/50)
        "selic": 0.145,
    }
    taxa_capm = 0.16

    wacc_sem_cambio = calcular_wacc(dados_mock, taxa_capm, pct_divida_moeda_estrangeira=0.0)
    wacc_com_cambio = calcular_wacc(dados_mock, taxa_capm, pct_divida_moeda_estrangeira=90.0)

    # Racional (90% em moeda estrangeira):
    # spread_cambial = 0.9 * 2.5% = 2.25%
    # Kd = 14.5% + 3% + 2.25% = 19.75% -> pós-imposto = 19.75% * (1-0.34) = 13.035%
    # WACC = (0.5 * 16%) + (0.5 * 13.035%) = 8% + 6.5175% = 14.5175%
    assert wacc_com_cambio == pytest.approx(0.145175)
    assert wacc_com_cambio > wacc_sem_cambio
    assert wacc_sem_cambio == pytest.approx(0.13775)  # idêntico ao cenário sem ajuste cambial