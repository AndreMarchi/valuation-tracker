# Taxa Selic atual — atualizar periodicamente
# Fonte: https://www.bcb.gov.br
SELIC_ANUAL = 0.1475  # 14.75% ao ano (maio 2026)

# Prêmio de risco histórico do mercado brasileiro
PREMIO_RISCO_MERCADO = 0.05  # 5% ao ano

# Beta padrão por setor quando não disponível
BETA_POR_SETOR = {
    "Intermediários Financeiros": 0.85,
    "Bancos":                     0.85,
    "Energia Elétrica":           0.65,
    "Petróleo, Gás e Biocombustíveis": 1.10,
    "Varejo":                     1.20,
    "Tecnologia":                 1.30,
    "Transporte Aéreo":           1.50,
    "Transporte":                 1.20,
    "Construção Civil":           1.10,
    "Alimentos":                  0.90,
    "Mineração":                  1.15,
    "Agronegócio":                0.95,
    "Siderurgia e Metalurgia":    1.10,
}
BETA_PADRAO = 1.0


def calcular_capm(setor: str, beta: float = None) -> dict:
    """
    Calcula a taxa de desconto pelo modelo CAPM.

    Taxa = Selic + Beta × Prêmio de Risco

    Args:
        setor: Setor da empresa
        beta:  Beta da empresa (opcional — usa padrão do setor se None)

    Returns:
        Dicionário com taxa de desconto e componentes do CAPM
    """

    beta_usado = beta if beta else BETA_POR_SETOR.get(setor, BETA_PADRAO)
    taxa_desconto = SELIC_ANUAL + beta_usado * PREMIO_RISCO_MERCADO

    return {
        "selic":           SELIC_ANUAL,
        "beta":            beta_usado,
        "premio_risco":    PREMIO_RISCO_MERCADO,
        "taxa_desconto":   round(taxa_desconto, 4),
        "taxa_desconto_pct": round(taxa_desconto * 100, 2),
    }