# Empresas com controle estatal ou risco político relevante
EMPRESAS_ESTATAIS = {
    "PETR3", "PETR4",  # Petrobras
    "BBAS3",           # Banco do Brasil
    "ELET3", "ELET6",  # Eletrobras
    "SANB3", "SANB4", "SANB11",  # Santander (regulado)
    "CMIG3", "CMIG4",  # Cemig
    "CPLE3", "CPLE6",  # Copel
    "SAPR3", "SAPR4", "SAPR11",  # Sanepar
    "CSAN3",           # Cosan
}

# Setores com risco regulatório alto
SETORES_REGULADOS = {
    "Petróleo e Gás Integrado",
    "Energia Elétrica",
    "Saneamento",
    "Bancos",
    "Telecomunicações",
}

# Penalizações no score (0 a 10)
PENALIZACAO_ESTATAL   = 2.0
PENALIZACAO_REGULADO  = 1.0


def analisar_risco(ticker: str, setor: str, score_atual: float) -> dict:
    """
    Analisa riscos políticos e regulatórios e ajusta o score.

    Args:
        ticker: Código da ação (ex: PETR4)
        setor: Setor da empresa retornado pela Brapi
        score_atual: Score fundamentalista calculado (0-10)

    Returns:
        Dicionário com alertas, penalização e score ajustado
    """

    alertas = []
    penalizacao = 0.0
    is_estatal  = ticker.upper() in EMPRESAS_ESTATAIS
    is_regulado = setor in SETORES_REGULADOS

    if is_estatal:
        penalizacao += PENALIZACAO_ESTATAL
        alertas.append({
            "tipo":     "estatal",
            "nivel":    "alto",
            "titulo":   "Empresa com controle estatal",
            "descricao": (
                "O valuation fundamentalista pode não refletir riscos de "
                "interferência política na gestão, política de preços e "
                "distribuição de dividendos."
            ),
        })

    if is_regulado and not is_estatal:
        penalizacao += PENALIZACAO_REGULADO
        alertas.append({
            "tipo":     "regulatorio",
            "nivel":    "medio",
            "titulo":   "Setor com alto risco regulatório",
            "descricao": (
                "Empresas deste setor estão sujeitas a mudanças regulatórias "
                "que podem impactar significativamente receitas e margens."
            ),
        })

    score_ajustado = round(max(0.0, score_atual - penalizacao), 1)

    if score_ajustado >= 8:
        classificacao_ajustada = "Muito Atrativa"
    elif score_ajustado >= 6:
        classificacao_ajustada = "Atrativa"
    elif score_ajustado >= 4:
        classificacao_ajustada = "Neutra"
    else:
        classificacao_ajustada = "Cara / Evitar"

    return {
        "score_fundamentalista": score_atual,
        "penalizacao":           penalizacao,
        "score_ajustado":        score_ajustado,
        "classificacao_ajustada": classificacao_ajustada,
        "is_estatal":            is_estatal,
        "is_regulado":           is_regulado,
        "alertas":               alertas,
    }