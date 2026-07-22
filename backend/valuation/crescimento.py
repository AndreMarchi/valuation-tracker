# Thresholds para detectar empresa de crescimento
CRESCIMENTO_ALTO    = 0.15   # >15% ao ano
CRESCIMENTO_MEDIO   = 0.08   # >8% ao ano

# Médias setoriais de EV/Receita (PSR)
PSR_MEDIO_SETOR = {
    "Tecnologia":              3.0,
    "Material de Transporte":  1.5,
    "Saúde":                   2.0,
    "Varejo":                  0.8,
    "Alimentos":               0.6,
    "Construção Civil":        0.8,
}
PSR_MEDIO_PADRAO = 1.5


def detectar_fase_crescimento(crescimento_5a: float) -> str:
    """
    Detecta a fase de crescimento da empresa.

    Returns:
        'alto', 'medio' ou 'maduro'
    """
    if crescimento_5a >= CRESCIMENTO_ALTO:
        return "alto"
    elif crescimento_5a >= CRESCIMENTO_MEDIO:
        return "medio"
    return "maduro"


def calcular_peg_ratio(pl: float, crescimento_lucro: float) -> dict:
    """
    Calcula o PEG Ratio (Price/Earnings to Growth).
    Criado por Peter Lynch — corrige o P/L pelo crescimento.

    PEG = P/L ÷ Taxa de Crescimento (em %)

    PEG < 1.0 → barata considerando o crescimento
    PEG 1.0-2.0 → preço justo
    PEG > 2.0 → cara mesmo crescendo
    """

    if pl <= 0 or crescimento_lucro <= 0:
        return {
            "classificacao": "Não aplicável",
            "erro":          "PEG requer P/L e crescimento positivos",
            "peg":           None,
        }

    # Crescimento em percentual (ex: 0.20 → 20)
    crescimento_pct = crescimento_lucro * 100
    peg = pl / crescimento_pct

    if peg < 1.0:
        classificacao = "Descontada"
    elif peg <= 2.0:
        classificacao = "Neutra"
    else:
        classificacao = "Cara"

    return {
        "peg":            round(peg, 2),
        "pl":             pl,
        "crescimento_pct": round(crescimento_pct, 1),
        "classificacao":  classificacao,
        "interpretacao":  _interpretar_peg(peg),
    }


def _interpretar_peg(peg: float) -> str:
    if peg < 0.5:
        return "Muito descontada — crescimento não precificado"
    elif peg < 1.0:
        return "Descontada — crescimento subprecificado"
    elif peg <= 1.5:
        return "Preço justo pelo crescimento"
    elif peg <= 2.0:
        return "Levemente cara pelo crescimento"
    else:
        return "Cara — crescimento já precificado em excesso"


def calcular_ev_receita(
    psr_atual: float,
    setor: str,
    receita_12m: float,
    num_acoes: float,
    div_liquida: float,
    valor_mercado: float,
) -> dict:
    """
    Avalia a empresa pelo múltiplo EV/Receita (PSR).
    Útil para empresas de crescimento com margens baixas.
    """

    if psr_atual <= 0 or receita_12m <= 0:
        return {
            "classificacao": "Não aplicável",
            "erro":          "EV/Receita não calculável — dados insuficientes",
            "psr_atual":     psr_atual,
        }

    media_setor   = PSR_MEDIO_SETOR.get(setor, PSR_MEDIO_PADRAO)
    desconto      = ((media_setor - psr_atual) / media_setor) * 100

    # Preço justo pelo PSR médio do setor
    ev_justo      = receita_12m * media_setor
    equity_justo  = ev_justo - div_liquida
    preco_justo   = equity_justo / num_acoes if num_acoes > 0 else 0

    if desconto >= 20:
        classificacao = "Descontada"
    elif desconto >= 0:
        classificacao = "Neutra"
    else:
        classificacao = "Cara"

    return {
        "psr_atual":      round(psr_atual, 2),
        "psr_medio_setor": media_setor,
        "preco_justo":    round(preco_justo, 2) if preco_justo > 0 else None,
        "margem_seguranca": round(desconto, 2),
        "classificacao":  classificacao,
    }


def calcular_rule_of_40(crescimento_receita: float, margem_ebit: float) -> dict:
    """
    Rule of 40 — métrica para empresas de tecnologia e crescimento.
    Crescimento de receita + Margem EBIT deve ser >= 40%.

    >= 40% → empresa saudável
    < 40%  → empresa pode estar sacrificando margem demais
    """

    crescimento_pct = crescimento_receita * 100
    margem_pct      = margem_ebit * 100
    rule_of_40      = crescimento_pct + margem_pct

    if rule_of_40 >= 60:
        classificacao  = "Excelente"
        interpretacao  = "Empresa de crescimento de alta qualidade"
    elif rule_of_40 >= 40:
        classificacao  = "Saudável"
        interpretacao  = "Equilibrio saudável entre crescimento e rentabilidade"
    elif rule_of_40 >= 20:
        classificacao  = "Atenção"
        interpretacao  = "Crescimento ou margem abaixo do ideal"
    else:
        classificacao  = "Preocupante"
        interpretacao  = "Empresa sacrificando margem sem crescimento suficiente"

    return {
        "crescimento_pct":  round(crescimento_pct, 1),
        "margem_ebit_pct":  round(margem_pct, 1),
        "rule_of_40":       round(rule_of_40, 1),
        "classificacao":    classificacao,
        "interpretacao":    interpretacao,
    }


def calcular_dcf_duas_fases(
    lucro_por_acao: float,
    crescimento_fase1: float,
    anos_fase1: int,
    crescimento_fase2: float,
    ke: float,
    preco_atual: float,
) -> dict:
    """
    `ke`: custo de capital PRÓPRIO (CAPM), não a WACC — `lucro_por_acao`
    (LPA) já é um fluxo de EQUITY (pós-juros, pós-impostos, já líquido do
    que pertence aos credores), então precisa ser descontado ao Ke, nunca
    à WACC (que mistura dívida mais barata via tax shield e, numa empresa
    endividada, é sempre menor que o Ke — descontar equity à WACC infla o
    valor justo). Nome explícito (`ke`, não `taxa_desconto`) de propósito:
    o nome genérico é o que permitiu esse bug passar despercebido antes
    (mesmo nome usado em outros lugares do código pra WACC) — mesmo
    precedente de `valuation/fcfe_valuation.py::calcular_valuation_fcfe()`.
    Bug real, quantificado pra BEEF3 antes da correção: descontar à WACC
    em vez do Ke inflava o valor_intrínseco em +59,3% (R$11,87 vs R$7,45
    correto) — ver CONTEXT.md.
    """

    if lucro_por_acao <= 0:
        return {
            "classificacao": "Não aplicável",
            "erro":          "DCF duas fases requer LPA positivo",
            "valor_intrinseco": None,
            "cenarios": None,
        }

    def _calcular(cresc_f1: float) -> float:
        """Calcula o valor intrínseco para uma taxa de crescimento da fase 1."""
        vp = 0.0
        lpa = lucro_por_acao
        for ano in range(1, anos_fase1 + 1):
            lpa *= (1 + cresc_f1)
            vp  += lpa / (1 + ke) ** ano
        lpa_terminal   = lpa * (1 + crescimento_fase2)
        valor_terminal = lpa_terminal / (ke - crescimento_fase2)
        vp_terminal    = valor_terminal / (1 + ke) ** anos_fase1
        return vp + vp_terminal

    valor_base       = _calcular(crescimento_fase1)
    valor_otimista   = _calcular(min(crescimento_fase1 * 1.3, 0.35))
    valor_pessimista = _calcular(crescimento_fase1 * 0.7)

    margem_seguranca = ((valor_base - preco_atual) / preco_atual) * 100

    if margem_seguranca >= 20:
        classificacao = "Descontada"
    elif margem_seguranca >= 0:
        classificacao = "Neutra"
    else:
        classificacao = "Cara"

    return {
        "valor_intrinseco":  round(valor_base, 2),
        "margem_seguranca":  round(margem_seguranca, 2),
        "classificacao":     classificacao,
        "crescimento_fase1": round(crescimento_fase1 * 100, 1),
        "crescimento_fase2": round(crescimento_fase2 * 100, 1),
        "anos_fase1":        anos_fase1,
        "cenarios": {
            "otimista":   round(valor_otimista, 2),
            "base":       round(valor_base, 2),
            "pessimista": round(valor_pessimista, 2),
        }
    }