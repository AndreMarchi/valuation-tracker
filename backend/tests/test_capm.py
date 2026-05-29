import pytest
from unittest.mock import patch
from valuation.capm import calcular_capm

@pytest.fixture
def selic_fixa_14_5():
    """Mock para garantir que a Selic retorne sempre 14.50% nos testes."""
    with patch("valuation.capm.buscar_selic_atual", return_code=None) as mock:
        mock.return_value = 0.145
        yield mock

def test_capm_setor_defensivo(selic_fixa_14_5):
    """Energia Elétrica (Beta 0.65) deve calcular a taxa bruta sem estourar as travas."""
    # Racional: 14.50% + (0.65 * 3.0%) = 14.50% + 1.95% = 16.45%
    # Como o teto máximo é 16%, a trava deve atuar e reduzir para 16%
    resultado = calcular_capm(setor="Energia Elétrica")
    
    assert resultado["beta"] == 0.65
    assert resultado["taxa_desconto"] == 0.1600
    assert resultado["taxa_desconto_pct"] == 16.0

def test_capm_setor_agressivo_bate_no_teto(selic_fixa_14_5):
    """Setores com Beta alto devem ter a taxa limitada ao teto máximo de 16%."""
    # Racional: Tecnologia (Beta 1.30) -> 14.50% + (1.30 * 3.0%) = 18.40%
    # Deve cravar no teto de 16%
    resultado = calcular_capm(setor="Tecnologia")
    
    assert resultado["beta"] == 1.30
    assert resultado["taxa_desconto"] == 0.1600 

def test_capm_setor_nao_mapeado_usa_padrao(selic_fixa_14_5):
    """Setor inexistente deve usar o Beta padrão de 1.0."""
    # Racional: Beta 1.0 -> 14.50% + (1.0 * 3.0%) = 17.50%
    # Deve cravar no teto de 16% devido à Selic alta do cenário atual
    resultado = calcular_capm(setor="Setor Inexistente")
    
    assert resultado["beta"] == 1.0
    assert resultado["taxa_desconto"] == 0.1600

def test_capm_com_beta_manual(selic_fixa_14_5):
    """Se passarmos um beta manual baixo, o piso de 10% deve ser respeitado se necessário."""
    with patch("valuation.capm.buscar_selic_atual") as mock_selic:
        # Forçando uma Selic artificialmente baixa de 5% para testar o piso do modelo
        mock_selic.return_value = 0.05
        
        # Racional: 5.0% + (0.5 * 3.0%) = 5.0% + 1.5% = 6.5%
        # Deve cravar no piso mínimo de 10%
        resultado = calcular_capm(setor="Qualquer", beta=0.5)
        
        assert resultado["beta"] == 0.5
        assert resultado["taxa_desconto"] == 0.1000