# backend/valuation/dcf.py

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
    Calcula o valor intrínseco de uma ação pelo método DCF (Fluxo de Caixa Descontado)
    e gera uma Matriz de Sensibilidade bidimensional.
    """

    def _calcular_valor(taxa_cresc: float, taxa_desc: float) -> float:
        # Trava de segurança: O WACC nunca pode ser menor ou igual ao crescimento na perpetuidade, 
        # senão a fórmula matemática entra em divisão por zero ou gera valores negativos irreais.
        if taxa_desc <= taxa_crescimento_perpetuidade:
            return 0.0

        # Projeta o fluxo de caixa para cada ano e desconta ao presente
        valor_presente = 0.0
        fluxo = fluxo_caixa_atual

        for ano in range(1, anos_projecao + 1):
            fluxo *= (1 + taxa_cresc)
            valor_presente += fluxo / (1 + taxa_desc) ** ano

        # Valor terminal (Gordon Growth Model)
        fluxo_terminal = fluxo * (1 + taxa_crescimento_perpetuidade)
        valor_terminal = fluxo_terminal / (taxa_desc - taxa_crescimento_perpetuidade)
        valor_terminal_presente = valor_terminal / (1 + taxa_desc) ** anos_projecao

        valor_total = valor_presente + valor_terminal_presente
        
        return valor_total / num_acoes if num_acoes > 0 else 0.0

    # 1. Três cenários originais (Mantidos para compatibilidade com a interface atual)
    valor_base       = _calcular_valor(taxa_crescimento, taxa_desconto)
    valor_otimista   = _calcular_valor(taxa_crescimento * 1.3, taxa_desconto)
    valor_pessimista = _calcular_valor(taxa_crescimento * 0.7, taxa_desconto)

    # 2. Construção da Matriz de Sensibilidade (WACC vs Crescimento)
    passo = 0.02 # Variação de 2% para cima e para baixo
    
    # Colunas: WACC (-2%, Base, +2%)
    wacc_cenarios = [taxa_desconto - passo, taxa_desconto, taxa_desconto + passo]
    
    # Linhas: Crescimento (-2%, Base, +2%) - Do menor para o maior crescimento
    cresc_cenarios = [taxa_crescimento - passo, taxa_crescimento, taxa_crescimento + passo]

    matriz_sensibilidade = {
        "colunas_wacc": [round(w, 4) for w in wacc_cenarios],
        "linhas": []
    }

    for c in cresc_cenarios:
        linha = {
            "taxa_crescimento": round(c, 4),
            "valores": []
        }
        for w in wacc_cenarios:
            val = _calcular_valor(c, w)
            linha["valores"].append(round(val, 2))
            
        matriz_sensibilidade["linhas"].append(linha)

    # 3. Classificação e Margem de Segurança do Cenário Base
    margem_seguranca = ((valor_base - preco_atual) / preco_atual) * 100 if preco_atual > 0 else 0

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
        "matriz_sensibilidade": matriz_sensibilidade,
    }