import fundamentus


def buscar_dados_acao_fundamentus(ticker: str) -> dict:
    """
    Busca dados financeiros via Fundamentus.
    Síncrono, sem token, focado em B3.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3)

    Returns:
        Dicionário no mesmo formato dos outros providers
    """

    try:
        df   = fundamentus.get_papel(ticker.upper())
        dados = df.iloc[0]
    except Exception as e:
        raise ValueError(f"Ticker '{ticker}' não encontrado no Fundamentus: {e}")

    def parse_pct(valor) -> float:
        """Converte '6.8%' para 0.068."""
        try:
            return float(str(valor).replace('%', '').replace(',', '.').strip()) / 100
        except:
            return 0.0

    def parse_float(valor) -> float:
        try:
            return float(str(valor).replace(',', '.').strip())
        except:
            return 0.0

    preco          = parse_float(dados.get('Cotacao', 0))
    dividend_yield = parse_pct(dados.get('Div_Yield', 0))
    dividendo_anual = round(preco * dividend_yield, 2)
    lpa  = parse_float(dados.get('LPA', 0)) / 100
    vpa  = parse_float(dados.get('VPA', 0)) / 100
    pl   = parse_float(dados.get('PL', 0))  / 100
    pvp  = parse_float(dados.get('PVP', 0)) / 100
    num_acoes      = parse_float(dados.get('Nro_Acoes', 0))
    patrim_liq     = parse_float(dados.get('Patrim_Liq', 0))
    lucro_liq_12m  = parse_float(dados.get('Lucro_Liquido_12m', 0))
    ebit_12m       = parse_float(dados.get('EBIT_12m', 0))
    div_liq        = parse_float(dados.get('Div_Liquida', 0))
    ebitda         = ebit_12m * 1.2 if ebit_12m else 0  # estimativa
    divida_ebitda  = round(div_liq / ebitda, 2) if ebitda else 0

    # FCL estimado: Lucro Líquido 12m (Fundamentus não retorna FCL direto)
    fcl = lucro_liq_12m

    return {
        "ticker":           ticker.upper(),
        "nome":             str(dados.get('Empresa', '')),
        "setor":            str(dados.get('Setor', '')),
        "industria":        str(dados.get('Subsetor', '')),
        "preco_atual":      preco,
        "lpa":              lpa,
        "vpa":              vpa,
        "pl":               pl,
        "pvp":              pvp,
        "dividendo_anual":  dividendo_anual,
        "dividend_yield":   round(dividend_yield * 100, 2),
        "fluxo_caixa":      fcl,
        "num_acoes":        num_acoes,
        "roe":              round(parse_pct(dados.get('ROE', 0)) * 100, 2),
        "divida_ebitda":    divida_ebitda,
        "margem_lucro":     round(parse_pct(dados.get('Marg_Liquida', 0)) * 100, 2),
        "crescimento_receita_5a": parse_pct(dados.get('Cres_Rec_5a', 0)),
        "ev_ebitda":              parse_float(dados.get('EV_EBITDA', 0)) / 100,
        "ebit_12m":               parse_float(dados.get('EBIT_12m', 0)),
        "div_liquida":            parse_float(dados.get('Div_Liquida', 0)),
    }