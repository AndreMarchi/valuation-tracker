from dados.selic import buscar_selic_atual

# --- CONFIGURAÇÕES E PREMISSAS DO MODELO ---
PREMIO_RISCO_MERCADO = 0.03  # Adicional exigido para renda variável (3.0%)
TAXA_DESCONTO_MINIMA = 0.10  # Piso de segurança (10.0%)
TAXA_DESCONTO_MAXIMA = 0.16  # Teto de segurança (16.0%)

# Mapeamento do risco sistêmico por setor (Sensibilidade ao Ibovespa)
BETA_POR_SETOR = {
    "Intermediários Financeiros":      0.85,
    "Bancos":                          0.85,
    "Energia Elétrica":                0.65,  # Setor defensivo / previsível
    "Petróleo, Gás e Biocombustíveis": 1.10,  # Dependente de commodities / volátil
    "Varejo":                          1.20,  # Cíclico / sensível à economia
    "Tecnologia":                      1.30,  # Alta volatilidade / crescimento
    "Transporte Aéreo":                1.50,  # Altíssimo risco operacional e cambial
    "Transporte":                      1.20,
    "Construção Civil":                1.10,
    "Alimentos":                       0.90,
    "Mineração":                       1.15,
    "Agronegócio":                     0.95,
    "Siderurgia e Metalurgia":         1.10,
}
BETA_PADRAO = 1.0  # Caso o setor não esteja explicitamente mapeado


def resolver_beta(beta_bruto, setor: str) -> float:
    """
    Resolve o beta final a ser usado no CAPM. BETA_POR_SETOR só entra como
    fallback quando o dado realmente não veio da fonte (beta_bruto is None
    — ver dados/provider.py, yfinance_provider.py, yquery_provider.py, que
    agora retornam None nesse caso em vez de um 1.0 fixo indistinguível de
    dado real). Nunca sobrescreve um valor real, mesmo que pareça
    "estranho" (ex: beta de 0.26 da BEEF3, confirmado como dado genuíno do
    Yahoo, não uma falha de extração — ver CONTEXT.md) ou seja exatamente
    1.0 vindo da própria fonte.
    """
    if beta_bruto is not None:
        return beta_bruto
    return BETA_POR_SETOR.get(setor, BETA_PADRAO)


# backend/valuation/capm.py

def calcular_capm(setor: str, selic_atual: float, beta_ativo: float = 1.0, valor_mercado: float = 0.0) -> dict:
    """
    Calcula o Custo de Capital Próprio (CAPM) detalhando todos os prêmios de risco.
    Inclui cálculo dinâmico de Size Premium baseado no Valor de Mercado.
    """
    
    # 1. Taxa Livre de Risco (Rf) = Selic 
    rf = selic_atual if selic_atual else 0.105 
    
    # 2. Equity Risk Premium (ERP) - Prêmio por investir em ações
    erp = 0.055 
    
    # 3. Country Risk Premium - Prêmio de Risco Brasil
    country_risk = 0.025 
    
    # 4. SIZE PREMIUM DINÂMICO (Baseado no Valor de Mercado)
    # Quanto menor a empresa, maior o risco de iliquidez e volatilidade.
    if valor_mercado > 50_000_000_000:       # > R$ 50 Bilhões (Large Cap - Ex: PETR4, ITUB4)
        size_premium = 0.00                  # 0% de prêmio
    elif valor_mercado > 10_000_000_000:     # > R$ 10 Bilhões (Mid Cap - Ex: RENT3)
        size_premium = 0.01                  # 1% de prêmio
    elif valor_mercado > 2_000_000_000:      # > R$ 2 Bilhões (Small Cap - Ex: WIZC3)
        size_premium = 0.02                  # 2% de prêmio
    elif valor_mercado > 0:                  # < R$ 2 Bilhões (Micro Cap)
        size_premium = 0.035                 # 3.5% de prêmio
    else:
        size_premium = 0.015                 # Fallback caso falhe o valor de mercado
    
    # Trava de segurança para o Beta (Evita Betas absurdamente altos ou negativos)
    if beta_ativo is not None and -1.0 <= beta_ativo <= 4.0:
        beta = beta_ativo
    else:
        beta = 1.0

    # CAPM = Rf + (Beta * ERP) + Country Risk + Size Premium
    taxa_desconto = rf + (beta * erp) + country_risk + size_premium

    return {
        "selic": rf,                                   
        "rf_selic": round(rf * 100, 2),                
        "beta": round(beta, 2),
        "equity_risk_premium": round(erp * 100, 2),
        "country_risk": round(country_risk * 100, 2),
        "size_premium": round(size_premium * 100, 2),
        "taxa_desconto": round(taxa_desconto, 4),      
        "taxa_desconto_pct": round(taxa_desconto * 100, 2) 
    }