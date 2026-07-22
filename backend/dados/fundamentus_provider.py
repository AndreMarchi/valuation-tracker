# backend/dados/fundamentus_provider.py
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
    
    # Tratamento da decisão técnica para Embraer (EMBJ3 no Fundamentus)
    ticker_final = "EMBJ3" if ticker.upper() == "EMBR3" else ticker.upper()

    try:
        df = fundamentus.get_papel(ticker_final)
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

    preco = parse_float(dados.get('Cotacao', 0))
    dividend_yield = parse_pct(dados.get('Div_Yield', 0))
    dividendo_anual = round(preco * dividend_yield, 2)
    
    # Divisões por 100 aplicadas conforme decisões técnicas do projeto
    lpa = parse_float(dados.get('LPA', 0)) / 100
    vpa = parse_float(dados.get('VPA', 0)) / 100
    pl = parse_float(dados.get('PL', 0)) / 100
    pvp = parse_float(dados.get('PVP', 0)) / 100
    
    num_acoes = parse_float(dados.get('Nro_Acoes', 0))
    patrim_liq = parse_float(dados.get('Patrim_Liq', 0))
    lucro_liq_12m = parse_float(dados.get('Lucro_Liquido_12m', 0))
    ebit_12m = parse_float(dados.get('EBIT_12m', 0))
    div_liq = parse_float(dados.get('Div_Liquida', 0))
    ebitda = ebit_12m * 1.2 if ebit_12m else 0  # estimativa
    divida_ebitda = round(div_liq / ebitda, 2) if ebitda else 0

    # FCL estimado: Lucro Líquido 12m (Fundamentus não retorna FCL direto)
    fcl = lucro_liq_12m

    # Captura das chaves de setor e subsetor (indústria) direto do DataFrame do pacote fundamentus
    setor_original = str(dados.get('Setor', 'Geral'))
    subsetor_original = str(dados.get('Subsetor', 'Geral'))

    return {
        "ticker": ticker.upper(),
        "nome": str(dados.get('Empresa', '')),
        "setor": setor_original,
        "industria": subsetor_original,
        "preco_atual": preco,
        "lpa": lpa,
        "vpa": vpa,
        "pl": pl,
        "pvp": pvp,
        "dividendo_anual": dividendo_anual,
        "dividend_yield": round(dividend_yield * 100, 2),
        "fluxo_caixa": fcl,
        "patrim_liq": patrim_liq,
        "num_acoes": num_acoes,
        "roe": round(parse_pct(dados.get('ROE', 0)) * 100, 2),
        "divida_ebitda": divida_ebitda,
        "margem_lucro": round(parse_pct(dados.get('Marg_Liquida', 0)) * 100, 2),
        "crescimento_receita_5a": parse_pct(dados.get('Cres_Rec_5a', 0)),
        "ebit_12m": ebit_12m,
        "div_liquida": div_liq,
        "ev_ebitda": parse_float(dados.get('EV_EBITDA', 0)) / 100,
        "valor_firma": parse_float(dados.get('Valor_da_firma', 0)),
        "valor_mercado": parse_float(dados.get('Valor_de_mercado', 0)),
        "receita_liquida_12m": parse_float(dados.get('Receita_Liquida_12m', 0)),
        "marg_ebit": parse_pct(dados.get('Marg_EBIT', 0)),
        "marg_liquida": parse_pct(dados.get('Marg_Liquida', 0)),
        "psr": parse_float(dados.get('PSR', 0)) / 100
    }