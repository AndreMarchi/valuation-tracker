def analisar_endividamento(
    div_liquida: float,
    ebit_12m: float,
    patrim_liq: float,
    score_atual: float,
) -> dict:
    """
    Analisa o endividamento da empresa e ajusta o score.

    Args:
        div_liquida: Dívida líquida em reais
        ebit_12m:    EBIT dos últimos 12 meses
        patrim_liq:  Patrimônio líquido
        score_atual: Score fundamentalista atual

    Returns:
        Dicionário com análise de endividamento e score ajustado
    """

    alertas    = []
    penalizacao = 0.0

    # Calcula Dívida Líquida / EBIT
    if ebit_12m and ebit_12m > 0:
        div_ebit = div_liquida / ebit_12m
    else:
        div_ebit = 0

    # Calcula Dívida Líquida / Patrimônio
    if patrim_liq and patrim_liq > 0:
        div_patrim = div_liquida / patrim_liq
    else:
        div_patrim = 0

    # Penalização por Dívida/EBIT
    if div_ebit > 5:
        penalizacao += 2.5
        alertas.append({
            "tipo":     "endividamento_critico",
            "nivel":    "alto",
            "titulo":   "Endividamento crítico",
            "descricao": (
                f"Dívida Líquida/EBIT de {div_ebit:.1f}x está em nível crítico. "
                f"A empresa levaria mais de 5 anos de EBIT para quitar a dívida."
            ),
        })
    elif div_ebit > 3:
        penalizacao += 1.5
        alertas.append({
            "tipo":     "endividamento_alto",
            "nivel":    "medio",
            "titulo":   "Endividamento elevado",
            "descricao": (
                f"Dívida Líquida/EBIT de {div_ebit:.1f}x está acima do nível "
                f"considerado saudável (até 3x)."
            ),
        })
    elif div_ebit > 2:
        penalizacao += 0.5
        alertas.append({
            "tipo":     "endividamento_moderado",
            "nivel":    "baixo",
            "titulo":   "Endividamento moderado",
            "descricao": (
                f"Dívida Líquida/EBIT de {div_ebit:.1f}x está em nível moderado. "
                f"Acompanhar evolução."
            ),
        })

    # Penalização por Dívida/Patrimônio
    if div_patrim > 2:
        penalizacao += 1.0
        alertas.append({
            "tipo":     "alavancagem_alta",
            "nivel":    "medio",
            "titulo":   "Alta alavancagem financeira",
            "descricao": (
                f"Dívida Líquida representa {div_patrim:.1f}x o patrimônio líquido. "
                f"Empresa altamente alavancada."
            ),
        })

    score_ajustado = round(max(0.0, score_atual - penalizacao), 1)

    if score_ajustado >= 8:
        classificacao = "Muito Atrativa"
    elif score_ajustado >= 6:
        classificacao = "Atrativa"
    elif score_ajustado >= 4:
        classificacao = "Neutra"
    else:
        classificacao = "Cara / Evitar"

    return {
        "div_liquida_ebit":   round(div_ebit, 2),
        "div_liquida_patrim": round(div_patrim, 2),
        "penalizacao":        penalizacao,
        "score_ajustado":     score_ajustado,
        "classificacao":      classificacao,
        "alertas":            alertas,
    }