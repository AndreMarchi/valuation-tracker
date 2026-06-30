import pytest
from valuation.capm import calcular_capm

SELIC_CENARIO_BASE = 0.1425  # Simulando um cenário de Selic a 14.25%

def test_capm_ativo_ultra_defensivo():
        """Ativos ultra-defensivos com beta próximo a zero devem manter seu risco real reduzido."""
        # Racional: 14.25% + (-0.01 * 5.5%) + 2.5% + 1.0% (Size Premium) = 17.70%
        resultado = calcular_capm(
            setor="Energia Elétrica",
            selic_atual=SELIC_CENARIO_BASE,
            beta_ativo=-0.01,
            valor_mercado=13_000_000_000
        )
        
        assert resultado["beta"] == -0.01
        assert resultado["taxa_desconto_pct"] == 17.70

def test_capm_ativo_agressivo():
        """Ativos de tecnologia com beta alto devem calcular o custo de capital sem tetos artificiais."""
        # Racional: 14.25% + (1.30 * 5.5%) + 2.5% + 2.0% (Size Premium) = 25.90%
        resultado = calcular_capm(
            setor="Tecnologia",
            selic_atual=SELIC_CENARIO_BASE,
            beta_ativo=1.30,
            valor_mercado=5_000_000_000
        )
        
        assert resultado["beta"] == 1.30
        assert resultado["taxa_desconto_pct"] == 25.90

def test_capm_sem_beta_informado_usa_padrao():
    """Caso o beta_ativo seja nulo, o sistema deve adotar o risco padrão de mercado (Beta 1.0)."""
    resultado = calcular_capm(
        setor="Qualquer", 
        selic_atual=SELIC_CENARIO_BASE, 
        beta_ativo=None,
        valor_mercado=60_000_000_000  # Mega Cap (Size Premium 0.0%)
    )
    
    assert resultado["beta"] == 1.0
    # 14.25% + (1.0 * 5.5%) + 2.5% + 0.0% = 22.25%
    assert resultado["taxa_desconto_pct"] == 22.25