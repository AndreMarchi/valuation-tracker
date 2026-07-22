# --- CONFIGURAÇÕES DE RISCO E GOVERNANÇA ---

# Empresas em Recuperação Judicial ou Estresse Financeiro Extremo (Armadilhas de Valor)
EMPRESAS_RECUPERACAO_JUDICIAL = {
    "LIGT3",  # Light
    "AMER3",  # Americanas
    "OIBR3",  # Oi
    "GOLL4",  # Gol
}

# Empresas com controle estatal ou risco político relevante
EMPRESAS_ESTATAIS = {
    "PETR3", "PETR4",            # Petrobras
    "BBAS3",                     # Banco do Brasil
    "ELET3", "ELET6",            # Eletrobras (Risco político residual/Lítios)
    "SANB3", "SANB4", "SANB11",  # Santander (Regulado corporativo)
    "CMIG3", "CMIG4",            # Cemig
    "CPLE3", "CPLE6",            # Copel
    "SAPR3", "SAPR4", "SAPR11",  # Sanepar
    "CSAN3",                     # Cosan
}

# Setores com risco regulatório alto
# "Bancos" e "Intermediários Financeiros" ficam juntos de propósito (mesmo
# padrão defensivo de valuation/setor.py, valuation/capm.py e
# valuation/ev_ebitda.py) — o setor real retornado por buscar_dados() pra
# bancos é "Intermediários Financeiros" (confirmado com ITUB4/BBAS3/BBDC4/
# SANB11), não "Bancos" (esse é o valor de industria/subsetor). Sem essa
# chave, is_regulado nunca disparava pra bancos não-estatais (ITUB4/BBDC4),
# perdendo a penalização de 1.0 ponto que o set já pretendia aplicar. Ver
# CONTEXT.md.
SETORES_REGULADOS = {
    "Petróleo e Gás Integrado",
    "Energia Elétrica",
    "Saneamento",
    "Bancos",
    "Intermediários Financeiros",
    "Telecomunicações",
}

# Penalizações no score (Escala de 0 a 10)
PENALIZACAO_RECUPERACAO_JUDICIAL = 6.0  # Penalização pesada para neutralizar distorções contábeis
PENALIZACAO_ESTATAL              = 2.0
PENALIZACAO_REGULADO             = 1.0


def analisar_risco(ticker: str, setor: str, score_atual: float) -> dict:
    """
    Analisa riscos políticos, regulatórios e de governança corporativa,
    ajustando o score final para neutralizar armadilhas de valor (Value Traps).

    Args:
        ticker: Código da ação (ex: LIGT3)
        setor: Setor da empresa retornado pela API/Provider
        score_atual: Score fundamentalista calculado originalmente (0-10)

    Returns:
        Dicionário com alertas estruturados, penalizações e classificação ajustada.
    """
    ticker_upper = ticker.upper()
    alertas = []
    penalizacao = 0.0
    
    # Flags de validação
    is_recuperacao = ticker_upper in EMPRESAS_RECUPERACAO_JUDICIAL
    is_estatal     = ticker_upper in EMPRESAS_ESTATAIS
    is_regulado    = setor in SETORES_REGULADOS

    # 1. Filtro Crítico: Recuperação Judicial (Sobrepõe os múltiplos quantitativos)
    if is_recuperacao:
        penalizacao += PENALIZACAO_RECUPERACAO_JUDICIAL
        alertas.append({
            "tipo": "recuperacao_judicial",
            "nivel": "critico",
            "titulo": "Empresa em Recuperação Judicial",
            "descricao": (
                "🔴 CRÍTICO: Os múltiplos contábeis baixos ou fórmulas tradicionais "
                "geram uma falsa ilusão de barganha. O risco de insolvência, litígios "
                "e diluição extrema do acionista desvalidam o valuation padrão."
            ),
        })

    # 2. Filtro Político: Controle Estatal
    if is_estatal:
        penalizacao += PENALIZACAO_ESTATAL
        alertas.append({
            "tipo": "estatal",
            "nivel": "alto",
            "titulo": "Empresa com controle estatal",
            "descricao": (
                "O valuation fundamentalista pode não refletir riscos de "
                "interferência política na gestão, política de preços e "
                "distribuição de dividendos."
            ),
        })

    # 3. Filtro Regulatório: Setores sob forte tutela do Governo
    if is_regulado and not is_estatal:
        penalizacao += PENALIZACAO_REGULADO
        alertas.append({
            "tipo": "regulatorio",
            "nivel": "medio",
            "titulo": "Setor com alto risco regulatório",
            "descricao": (
                "Empresas deste setor estão sujeitas a mudanças regulatórias "
                "que podem impactar significativamente receitas e margens."
            ),
        })

    # Cálculo do score ajustado final respeitando o piso de 0.0
    score_ajustado = round(max(0.0, score_atual - penalizacao), 1)

    # 4. Classificação Dinâmica de Atratividade
    if is_recuperacao:
        classificacao_ajustada = "Alto Risco / Evitar"
    elif score_ajustado >= 8:
        classificacao_ajustada = "Muito Atrativa"
    elif score_ajustado >= 6:
        classificacao_ajustada = "Atrativa"
    elif score_ajustado >= 4:
        classificacao_ajustada = "Neutra"
    else:
        classificacao_ajustada = "Cara / Evitar"

    return {
        "score_fundamentalista":   score_atual,
        "penalizacao":             penalizacao,
        "score_ajustado":          score_ajustado,
        "classificacao_ajustada":  classificacao_ajustada,
        "em_recuperacao_judicial": is_recuperacao,
        "is_estatal":              is_estatal,
        "is_regulado":             is_regulado,
        "alertas":                 alertas,
    }