def calcular_dcf(
    fluxo_caixa_atual: float,
    taxa_crescimento: float,
    taxa_desconto: float,
    anos_projecao: int,
    taxa_crescimento_perpetuidade: float,
    num_acoes: float,
    preco_atual: float,
) -> dict:
    """
    Calcula o valor intrínseco de uma ação pelo método DCF
    (Fluxo de Caixa Descontado).

    Args:
        fluxo_caixa_atual: Fluxo de caixa livre atual da empresa (em milhões)
        taxa_crescimento: Taxa de crescimento anual esperada (ex: 0.10 = 10%)
        taxa_desconto: Taxa de desconto / custo de capital (ex: 0.12 = 12%)
        anos_projecao: Número de anos para projeção (recomendado: 5 a 10)
        taxa_crescimento_perpetuidade: Taxa de crescimento na perpetuidade (ex: 0.03)
        num_acoes: Número total de ações da empresa (em milhões)
        preco_atual: Preço atual da ação na bolsa

    Returns:
        Dicionário com valor intrínseco por ação, margem de segurança e cenários
    """

    def _calcular_valor(taxa_cresc: float) -> float:
        # Projeta o fluxo de caixa para cada ano e desconta ao presente
        valor_presente = 0.0
        fluxo = fluxo_caixa_atual

        for ano in range(1, anos_projecao + 1):
            fluxo *= (1 + taxa_cresc)
            valor_presente += fluxo / (1 + taxa_desconto) ** ano

        # Valor terminal (Gordon Growth Model)
        fluxo_terminal = fluxo * (1 + taxa_crescimento_perpetuidade)
        valor_terminal = fluxo_terminal / (taxa_desconto - taxa_crescimento_perpetuidade)
        valor_terminal_presente = valor_terminal / (1 + taxa_desconto) ** anos_projecao

        valor_total = valor_presente + valor_terminal_presente
        return valor_total / num_acoes

    # Três cenários
    valor_base       = _calcular_valor(taxa_crescimento)
    valor_otimista   = _calcular_valor(taxa_crescimento * 1.3)
    valor_pessimista = _calcular_valor(taxa_crescimento * 0.7)

    margem_seguranca = ((valor_base - preco_atual) / preco_atual) * 100

    if margem_seguranca >= 20:
        classificacao = "Descontada"
    elif margem_seguranca >= 0:
        classificacao = "Neutra"
    else:
        classificacao = "Cara"

    return {
        "preco_atual": preco_atual,
        "valor_intrinseco": round(valor_base, 2),
        "margem_seguranca": round(margem_seguranca, 2),
        "classificacao": classificacao,
        "cenarios": {
            "otimista":   round(valor_otimista, 2),
            "base":       round(valor_base, 2),
            "pessimista": round(valor_pessimista, 2),
        },
    }