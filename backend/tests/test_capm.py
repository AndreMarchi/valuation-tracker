import pytest
from valuation.capm import calcular_capm, resolver_beta, BETA_POR_SETOR, BETA_PADRAO

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


# ─── resolver_beta() — BETA_POR_SETOR só como fallback de dado AUSENTE ─────
# Achado real: BETA_POR_SETOR estava calibrado mas nunca era consultado —
# calcular_capm() sempre usava beta_ativo direto do provider, sem fallback
# setorial. Decisão: usar a tabela SÓ quando o beta realmente não vier da
# fonte (None) — nunca pra "corrigir" um valor real que pareça estranho
# (ex: beta de 0.26 da BEEF3, já confirmado como dado genuíno do Yahoo em
# investigação anterior, ver CONTEXT.md). Termos usados no enunciado do bug:
# (a) beta ausente, (b) beta real = 1.0, (c) beta real ≠ 1.0 (BEEF3).

class TestResolverBeta:

    def test_a_beta_ausente_usa_fallback_do_setor_mapeado(self):
        assert resolver_beta(None, "Intermediários Financeiros") == BETA_POR_SETOR["Intermediários Financeiros"]
        assert resolver_beta(None, "Tecnologia") == BETA_POR_SETOR["Tecnologia"]

    def test_a_beta_ausente_setor_sem_mapeamento_usa_beta_padrao(self):
        assert resolver_beta(None, "Setor Sem Mapeamento Nenhum") == BETA_PADRAO

    def test_b_beta_real_igual_a_1_nao_e_tratado_como_ausente(self):
        # 1.0 vindo da fonte é um valor real, não deve ser trocado por
        # BETA_POR_SETOR mesmo que o setor tenha uma entrada diferente.
        assert resolver_beta(1.0, "Intermediários Financeiros") == 1.0

    def test_c_beta_real_diferente_de_1_permanece_intacto(self):
        # Réplica do caso real: BEEF3, beta = 0.26, confirmado como dado
        # genuíno do Yahoo (não um erro de extração) numa investigação
        # anterior — BETA_POR_SETOR não deve "corrigir" isso.
        assert resolver_beta(0.26, "Alimentos") == 0.26

    def test_beta_zero_e_um_valor_real_nao_ausente(self):
        # 0.0 é falsy em Python — guard explícito contra "if not beta_bruto"
        # (que trocaria um beta real de 0.0 pelo fallback por engano).
        assert resolver_beta(0.0, "Tecnologia") == 0.0