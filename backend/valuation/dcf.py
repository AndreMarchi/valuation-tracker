# backend/valuation/dcf.py

def calcular_dcf(
    fluxo_caixa_atual: float,
    taxa_crescimento: float,
    taxa_desconto: float,
    anos_projecao: int,
    taxa_crescimento_perpetuidade: float,
    num_acoes: float,
    preco_atual: float,
    divida_liquida: float = 0.0,
) -> dict:
    """
    Calcula o valor intrínseco de uma ação pelo método DCF (Fluxo de Caixa Descontado)
    e gera uma Matriz de Sensibilidade bidimensional.

    `fluxo_caixa_atual` é baseado em NOPAT (ver valuation/nopat.py) — exclui
    juros de propósito, é o fluxo correto pra descontar à WACC e chegar no
    valor da EMPRESA inteira (Enterprise Value = dívida + patrimônio), não
    direto no valor do equity. `divida_liquida` é subtraída do EV ANTES de
    dividir por `num_acoes`, pra chegar no Equity Value por ação — o número
    que de fato é comparável ao `preco_atual` (preço de uma ação, i.e.
    equity). Sem essa subtração, `valor_intrinseco` era Enterprise Value por
    ação sendo comparado com preço de equity — bug estrutural que inflava o
    valor justo proporcionalmente à alavancagem de cada empresa (BEEF3,
    Dívida Líquida/EBIT ~3,5x, era o caso mais distorcido — ver CONTEXT.md).

    IMPORTANTE — unidades: `divida_liquida` precisa vir na MESMA escala que
    `fluxo_caixa_atual`/`num_acoes` (R$ milhões, já divididos por 1_000_000
    pelos call sites em main.py/scanner/trabalhador.py) — nunca em R$ absolutos.
    `divida_liquida=0.0` (default) preserva exatamente o comportamento antigo.
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

        valor_total = valor_presente + valor_terminal_presente  # Enterprise Value (dívida + patrimônio)

        # EV -> Equity Value: subtrai a dívida líquida ANTES de dividir por
        # ação, senão o resultado mistura o que pertence aos credores com o
        # que pertence aos acionistas (ver docstring da função).
        valor_equity = valor_total - divida_liquida

        return valor_equity / num_acoes if num_acoes > 0 else 0.0

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