import pytest
from valuation.nopat import calcular_fcl_via_nopat

def test_nopat_calculo_alimentos_processados():
    """Garante que aplica o imposto de 34% e o fator de 50% para Alimentos Processados (JBSS3)."""
    dados_mock = {
        "ebit_12m": 10_000_000,  # 10 Milhões de EBIT
        "setor": "Alimentos Processados"
    }
    # Racional: 10M * 0.66 = 6.6M (NOPAT) -> 6.6M * 0.50 = 3.3M -> Escala: 3.3
    fcl = calcular_fcl_via_nopat(dados_mock)
    assert fcl == pytest.approx(3.3)

def test_nopat_calculo_transporte_aereo():
    """Valida o fator rigoroso de 20% para setores de Capex crítico como aviação."""
    dados_mock = {
        "ebit_12m": 10_000_000,
        "setor": "Transporte Aéreo"
    }
    # Racional: 10M * 0.66 = 6.6M (NOPAT) -> 6.6M * 0.20 = 1.32M -> Escala: 1.32
    fcl = calcular_fcl_via_nopat(dados_mock)
    assert fcl == pytest.approx(1.32)

def test_nopat_setor_nao_mapeado_usa_padrao():
    """Setores novos devem cair no fallback padrão de 65%."""
    dados_mock = {
        "ebit_12m": 10_000_000,
        "setor": "Setor Novo Qualquer"
    }
    # Racional: 10M * 0.66 = 6.6M (NOPAT) -> 6.6M * 0.65 = 4.29M -> Escala: 4.29
    fcl = calcular_fcl_via_nopat(dados_mock)
    assert fcl == pytest.approx(4.29)