from dados.selic import buscar_selic_atual

PREMIO_RISCO_MERCADO = 0.03
TAXA_DESCONTO_MAXIMA = 0.16
TAXA_DESCONTO_MINIMA = 0.10

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
    Selic atualizada automaticamente via API do BACEN.
    """

    selic = buscar_selic_atual()
    beta_usado = beta if beta else BETA_POR_SETOR.get(setor, BETA_PADRAO)
    taxa_desconto = selic + beta_usado * PREMIO_RISCO_MERCADO

    # Aplica teto e piso
    taxa_desconto = max(TAXA_DESCONTO_MINIMA, min(taxa_desconto, TAXA_DESCONTO_MAXIMA))

    return {
        "selic":             round(selic, 4),
        "beta":              beta_usado,
        "premio_risco":      PREMIO_RISCO_MERCADO,
        "taxa_desconto":     round(taxa_desconto, 4),
        "taxa_desconto_pct": round(taxa_desconto * 100, 2),
    }