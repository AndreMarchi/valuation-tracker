import pytest
from valuation.bazin import calcular_bazin


def test_bazin_acao_descontada():
    """Ação pagando dividendos acima do mínimo esperado."""
    resultado = calcular_bazin(dividendo_anual=3.0, preco_atual=40.0)
    assert resultado["preco_justo"] == 50.0
    assert resultado["classificacao"] == "Descontada"
    assert resultado["margem_seguranca"] == 25.0


def test_bazin_acao_cara():
    """Ação com dividendo baixo em relação ao preço."""
    resultado = calcular_bazin(dividendo_anual=1.0, preco_atual=30.0)
    assert resultado["classificacao"] == "Cara"
    assert resultado["margem_seguranca"] < 0


def test_bazin_acao_neutra():
    """Ação exatamente no preço justo."""
    resultado = calcular_bazin(dividendo_anual=3.0, preco_atual=50.0)
    assert resultado["classificacao"] == "Neutra"
    assert resultado["margem_seguranca"] == 0.0


def test_bazin_sem_dividendos():
    """Bazin não se aplica a empresas sem dividendos."""
    resultado = calcular_bazin(dividendo_anual=0, preco_atual=30.0)
    assert resultado["classificacao"] == "Não aplicável"
    assert resultado["preco_justo"] is None


def test_bazin_yield_personalizado():
    """Usuário pode definir um yield mínimo diferente de 6%."""
    resultado = calcular_bazin(dividendo_anual=3.0, preco_atual=40.0, 
                               yield_minimo=0.08)
    assert resultado["preco_justo"] == 37.5
    assert resultado["classificacao"] == "Cara"


def test_bazin_dividend_yield_calculado():
    """Dividend yield atual deve ser calculado corretamente."""
    resultado = calcular_bazin(dividendo_anual=3.0, preco_atual=50.0)
    assert resultado["dividend_yield"] == 6.0