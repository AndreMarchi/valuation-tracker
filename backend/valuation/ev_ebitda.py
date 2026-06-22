# Médias setoriais de EV/EBITDA — referência Kobori
EV_EBITDA_MEDIO_SETOR = {
    "Intermediários Financeiros": 8.0,
    "Bancos":                     8.0,
    "Energia Elétrica":           7.0,
    "Petróleo, Gás e Biocombustíveis": 5.0,
    "Varejo":                     9.0,
    "Tecnologia":                 15.0,
    "Transporte Aéreo":           6.0,
    "Transporte":                 7.0,
    "Construção Civil":           8.0,
    "Alimentos":                  8.0,
    "Mineração":                  5.0,
    "Agronegócio":                7.0,
    "Siderurgia e Metalurgia":    5.0,
}
EV_EBITDA_MEDIO_PADRAO = 8.0


# backend/valuation/ev_ebitda.py

def calcular_ev_ebitda(
    ev_ebitda_atual: float, 
    ev_ebitda_historico: float, # O múltiplo que a empresa costuma negociar
    ev_ebitda_setor: float,     # A média do setor
    ebit_12m: float, 
    num_acoes: float, 
    div_liquida: float
) -> dict:
    """
    Calcula o preço justo por EV/EBITDA usando uma âncora híbrida (50% Empresa / 50% Setor)
    para evitar inflar o preço alvo de empresas ineficientes.
    """
    if ev_ebitda_atual <= 0 or ebit_12m <= 0 or num_acoes <= 0:
        return {
            "ev_ebitda_atual": ev_ebitda_atual,
            "preco_justo": None,
            "classificacao": "Não aplicável",
            "erro": "EBITDA ou Múltiplo atual negativo/inválido."
        }

    # Tratamento de segurança caso o histórico ou o setor não existam
    hist = ev_ebitda_historico if ev_ebitda_historico > 0 else ev_ebitda_atual
    setor = ev_ebitda_setor if ev_ebitda_setor > 0 else hist

    # A Mágica Institucional: Blend 50/50
    multiplo_alvo = (hist * 0.5) + (setor * 0.5)

    # EV Alvo = EBITDA * Múltiplo Alvo
    ev_alvo = ebit_12m * multiplo_alvo
    
    # Preço Justo = (EV Alvo - Dívida Líquida) / Número de Ações
    valor_mercado_alvo = ev_alvo - div_liquida
    preco_justo = valor_mercado_alvo / num_acoes if valor_mercado_alvo > 0 else 0.0

    if ev_ebitda_atual < multiplo_alvo * 0.8:
        classificacao = "Descontada"
    elif ev_ebitda_atual > multiplo_alvo * 1.2:
        classificacao = "Cara"
    else:
        classificacao = "Neutra"

    return {
        "ev_ebitda_atual": round(ev_ebitda_atual, 2),
        "ev_ebitda_alvo_blend": round(multiplo_alvo, 2),
        "preco_justo": round(preco_justo, 2),
        "classificacao": classificacao
    }