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


def calcular_ev_ebitda(
    ev_ebitda_atual: float,
    setor: str,
    ebit_12m: float,
    num_acoes: float,
    div_liquida: float,
) -> dict:
    """
    Avalia a empresa pelo múltiplo EV/EBITDA comparado à média setorial.

    Args:
        ev_ebitda_atual: EV/EBITDA atual da empresa
        setor:           Setor da empresa
        ebit_12m:        EBIT dos últimos 12 meses
        num_acoes:       Número total de ações
        div_liquida:     Dívida líquida

    Returns:
        Dicionário com análise EV/EBITDA e preço justo estimado
    """

    if ev_ebitda_atual <= 0 or ebit_12m <= 0 or num_acoes <= 0:
        return {
            "classificacao":    "Não aplicável",
            "erro":             "EV/EBITDA não calculável — dados insuficientes",
            "ev_ebitda_atual":  ev_ebitda_atual,
            "ev_ebitda_medio":  None,
            "preco_justo":      None,
            "margem_seguranca": None,
        }

    # EBITDA estimado como EBIT × 1.2 (aproximação)
    ebitda_estimado = ebit_12m * 1.2

    media_setor = EV_EBITDA_MEDIO_SETOR.get(setor, EV_EBITDA_MEDIO_PADRAO)

    # Preço justo pelo EV/EBITDA setorial
    ev_justo      = ebitda_estimado * media_setor
    equity_justo  = ev_justo - div_liquida
    preco_justo   = equity_justo / num_acoes if num_acoes > 0 else 0

    desconto = ((ev_justo - (ebitda_estimado * ev_ebitda_atual)) /
                (ebitda_estimado * ev_ebitda_atual)) * 100

    if desconto >= 20:
        classificacao = "Descontada"
    elif desconto >= 0:
        classificacao = "Neutra"
    else:
        classificacao = "Cara"

    return {
        "ev_ebitda_atual":   round(ev_ebitda_atual, 2),
        "ev_ebitda_medio":   media_setor,
        "ebitda_estimado":   round(ebitda_estimado / 1_000_000, 2),
        "preco_justo":       round(preco_justo, 2) if preco_justo > 0 else None,
        "margem_seguranca":  round(desconto, 2),
        "classificacao":     classificacao,
    }