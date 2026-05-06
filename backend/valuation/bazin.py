def calcular_bazin(dividendo_anual: float, preco_atual: float, 
                   yield_minimo: float = 0.06) -> dict:
    """
    Calcula o preço justo de uma ação pelo método Bazin.

    Fórmula: Preço Justo = Dividendo Anual Por Ação ÷ Yield Mínimo

    Args:
        dividendo_anual: Total de dividendos pagos por ação nos últimos 12 meses
        preco_atual: Preço atual da ação na bolsa
        yield_minimo: Rendimento mínimo esperado (padrão: 6% ao ano)

    Returns:
        Dicionário com preço justo, dividend yield atual e classificação
    """

    if dividendo_anual <= 0:
        return {
            "erro": "Bazin não se aplica a empresas que não pagam dividendos",
            "preco_justo": None,
            "dividend_yield": None,
            "margem_seguranca": None,
            "classificacao": "Não aplicável",
        }

    preco_justo = dividendo_anual / yield_minimo
    dividend_yield = (dividendo_anual / preco_atual) * 100
    margem_seguranca = ((preco_justo - preco_atual) / preco_atual) * 100

    if margem_seguranca >= 20:
        classificacao = "Descontada"
    elif margem_seguranca >= 0:
        classificacao = "Neutra"
    else:
        classificacao = "Cara"

    return {
        "preco_justo": round(preco_justo, 2),
        "preco_atual": preco_atual,
        "dividend_yield": round(dividend_yield, 2),
        "margem_seguranca": round(margem_seguranca, 2),
        "classificacao": classificacao,
    }