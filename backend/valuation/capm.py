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


def calcular_capm(setor: str, beta: float = None) -> dict:
    """
    Calcula a taxa de desconto de uma ação utilizando o modelo CAPM.
    
    O CAPM (Capital Asset Pricing Model) define o retorno mínimo exigido 
    pelos acionistas ponderando o retorno livre de risco e a volatilidade do setor.
    
    A Taxa Selic é atualizada de forma automática consultando a API do BACEN.
    
    CONCEITOS CHAVE:
    ----------------
    - Selic: Custo de oportunidade básico da renda fixa nacional.
    - Prêmio de Risco: O "plus" matemático para justificar o risco de bolsa.
    - Beta (β): Risco sistêmico. Valores abaixo de 1.0 são defensivos (ex: Energia);
                valores acima de 1.0 são agressivos/voláteis (ex: Tecnologia).
    
    Fórmula:
    --------
    Taxa Bruta = Selic + (Beta * Prêmio de Risco)
    """
    # 1. Captura da taxa livre de risco em tempo real
    selic = buscar_selic_atual()
    
    # 2. Atribuição do Beta (Usa o parâmetro manual se fornecido, senão busca o setorial)
    beta_usado = beta if beta else BETA_POR_SETOR.get(setor, BETA_PADRAO)
    
    # 3. Aplicação da equação clássica do CAPM
    taxa_desconto = selic + (beta_usado * PREMIO_RISCO_MERCADO)

    # 4. Filtro de Consistência (Aplica as travas de teto e piso estipuladas)
    taxa_desconto = max(TAXA_DESCONTO_MINIMA, min(taxa_desconto, TAXA_DESCONTO_MAXIMA))

    return {
        "selic":             round(selic, 4),
        "beta":              beta_usado,
        "premio_risco":      PREMIO_RISCO_MERCADO,
        "taxa_desconto":     round(taxa_desconto, 4),
        "taxa_desconto_pct": round(taxa_desconto * 100, 2),
    }