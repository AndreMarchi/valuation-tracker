import pytest
from valuation.graham import calcular_graham


def test_graham_acao_descontada():
    """Ação cujo preço justo está bem acima do preço atual."""
    resultado = calcular_graham(lpa=5.0, vpa=20.0, preco_atual=30.0)
    assert resultado["preco_justo"] == 47.43
    assert resultado["classificacao"] == "Descontada"
    assert resultado["margem_seguranca"] > 20


def test_graham_acao_cara():
    """Ação cujo preço atual está acima do preço justo."""
    resultado = calcular_graham(lpa=2.0, vpa=10.0, preco_atual=50.0)
    assert resultado["classificacao"] == "Cara"
    assert resultado["margem_seguranca"] < 0


def test_graham_acao_neutra():
    """Ação próxima ao preço justo."""
    resultado = calcular_graham(lpa=3.0, vpa=15.0, preco_atual=31.0)
    assert resultado["classificacao"] == "Neutra"


def test_graham_lpa_negativo():
    """Graham não se aplica quando LPA é negativo."""
    resultado = calcular_graham(lpa=-2.0, vpa=15.0, preco_atual=20.0)
    assert resultado["classificacao"] == "Não aplicável"
    assert resultado["preco_justo"] is None


def test_graham_vpa_negativo():
    """Graham não se aplica quando VPA é negativo."""
    resultado = calcular_graham(lpa=3.0, vpa=-5.0, preco_atual=20.0)
    assert resultado["classificacao"] == "Não aplicável"