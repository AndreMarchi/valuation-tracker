import yfinance as yf
from dados.fundamentus_provider import buscar_dados_acao_fundamentus


def buscar_historico_5a(ticker: str) -> dict:
    """
    Busca histórico de preços dos últimos 5 anos via yfinance
    e crescimento de receita via Fundamentus.

    Args:
        ticker: Código da ação (ex: BBDC3, PETR4)

    Returns:
        Dicionário com dados históricos e alertas
    """

    ticker_upper = ticker.upper().strip()
    ticker_sa    = f"{ticker_upper}.SA"

    # Histórico de preços via yfinance
    try:
        ativo = yf.Ticker(ticker_sa)
        hist  = ativo.history(period="5y")

        if hist.empty:
            raise ValueError("Histórico vazio")

        preco_minimo  = round(float(hist['Low'].min()), 2)
        preco_maximo  = round(float(hist['High'].max()), 2)
        preco_medio   = round(float(hist['Close'].mean()), 2)
        preco_atual   = round(float(hist['Close'].iloc[-1]), 2)

    except Exception as e:
        print(f"Histórico yfinance falhou para {ticker_upper}: {e}")
        preco_minimo = None
        preco_maximo = None
        preco_medio  = None
        preco_atual  = None

    # Crescimento de receita via Fundamentus
    try:
        dados_fund = buscar_dados_acao_fundamentus(ticker_upper)
        crescimento_receita_5a = dados_fund.get("crescimento_receita_5a", 0)
    except Exception:
        crescimento_receita_5a = None

    return {
        "preco_minimo_5a":       preco_minimo,
        "preco_maximo_5a":       preco_maximo,
        "preco_medio_5a":        preco_medio,
        "preco_atual_referencia": preco_atual,
        "crescimento_receita_5a": crescimento_receita_5a,
    }


def gerar_alertas_historicos(
    historico: dict,
    dcf: dict,
    graham: dict,
    bazin: dict,
) -> list:
    """
    Gera alertas quando o valuation ultrapassa limites históricos.
    """

    alertas = []
    maximo  = historico.get("preco_maximo_5a")
    medio   = historico.get("preco_medio_5a")

    if maximo is None:
        return alertas

    # Verifica DCF
    dcf_otimista = (dcf.get("cenarios") or {}).get("otimista")
    dcf_base     = (dcf.get("cenarios") or {}).get("base")

    if dcf_base and dcf_base > maximo * 1.2:
        alertas.append({
            "tipo":     "dcf_acima_historico",
            "nivel":    "alto",
            "titulo":   "DCF muito acima do histórico",
            "descricao": (
                f"O valor intrínseco calculado (R$ {dcf_base:.2f}) está "
                f"{((dcf_base/maximo - 1)*100):.0f}% acima do preço máximo "
                f"dos últimos 5 anos (R$ {maximo:.2f}). "
                f"Considere revisar as premissas do DCF."
            ),
        })
    elif dcf_base and dcf_base > maximo:
        alertas.append({
            "tipo":     "dcf_acima_maximo",
            "nivel":    "medio",
            "titulo":   "DCF acima do máximo histórico",
            "descricao": (
                f"O valor intrínseco (R$ {dcf_base:.2f}) ultrapassa o preço "
                f"máximo dos últimos 5 anos (R$ {maximo:.2f}). "
                f"Use com cautela."
            ),
        })

    # Verifica Graham
    graham_justo = graham.get("preco_justo")
    if graham_justo and graham_justo > maximo * 1.2:
        alertas.append({
            "tipo":     "graham_acima_historico",
            "nivel":    "medio",
            "titulo":   "Graham acima do máximo histórico",
            "descricao": (
                f"O preço justo Graham (R$ {graham_justo:.2f}) está acima "
                f"do máximo histórico de 5 anos (R$ {maximo:.2f})."
            ),
        })

    # Crescimento negativo
    crescimento = historico.get("crescimento_receita_5a")
    if crescimento is not None and crescimento < -0.05:
        alertas.append({
            "tipo":     "crescimento_negativo",
            "nivel":    "medio",
            "titulo":   "Queda de receita nos últimos 5 anos",
            "descricao": (
                f"A empresa apresentou queda de receita de "
                f"{abs(crescimento*100):.1f}% ao ano nos últimos 5 anos. "
                f"As projeções do DCF podem estar superestimadas."
            ),
        })

    return alertas
