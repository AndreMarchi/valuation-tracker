# backend/dados/yquery_provider.py
from yahooquery import Ticker
import time
import pandas as pd

_cache: dict = {}
CACHE_DURACAO_SEGUNDOS = 600  # 10 minutos

def _cache_valido(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    idade = time.time() - _cache[ticker]["timestamp"]
    return idade < CACHE_DURACAO_SEGUNDOS

def _formatar_ticker_b3(ticker: str) -> str:
    ticker = ticker.upper().strip()
    # Adiciona o .SA para a B3 se já não existir
    if not ticker.endswith('.SA'):
        ticker = f"{ticker}.SA"
    return ticker

def _extrair_dado_yq(df, coluna: str) -> float:
    """
    Extrai o valor mais recente de uma coluna financeira do yahooquery.
    No yahooquery, as colunas são as métricas e as linhas são os anos/trimestres.
    """
    # Verifica se o DataFrame é válido e possui a coluna desejada
    if df is None or isinstance(df, dict) or df.empty or coluna not in df.columns:
        return 0.0
    try:
        # Pega todos os valores numéricos válidos da coluna e retorna o último (mais recente)
        valores_validos = df[coluna].dropna()
        if not valores_validos.empty:
            return float(valores_validos.iloc[-1])
        return 0.0
    except Exception:
        return 0.0

def buscar_dados_acao_yq(ticker: str) -> dict:
    """
    Busca dados fundamentalistas usando a biblioteca yahooquery (acesso direto à API JSON do Yahoo).
    """
    ticker_upper = ticker.upper().strip()

    if _cache_valido(ticker_upper):
        return _cache[ticker_upper]["dados"]

    ticker_formatado = _formatar_ticker_b3(ticker_upper)
    ativo = Ticker(ticker_formatado)

    # 1. DADOS DE PREÇO E RESUMO (Extração via Dicionários JSON puros)
    # yahooquery retorna dicts onde a chave primária é o ticker: {'PETR4.SA': {'regularMarketPrice': 40.0}}
    price_data = ativo.price.get(ticker_formatado, {})
    summary    = ativo.summary_detail.get(ticker_formatado, {})
    
    # Se o Yahoo não encontrar o ticker, ele retorna uma string no lugar do dict (ex: "No fundamentals data found")
    if isinstance(price_data, str) or not price_data:
        raise ValueError(f"Ticker '{ticker}' não encontrado no YahooQuery")

    preco = price_data.get('regularMarketPrice') or summary.get('previousClose') or 0
    if preco == 0:
        raise ValueError(f"Ticker '{ticker}' sem liquidez no momento (preço zerado)")

    # 2. DEMONSTRAÇÕES CONTÁBEIS (Retorna DataFrames do Pandas)
    dre     = ativo.income_statement()
    balanco = ativo.balance_sheet()
    caixa   = ativo.cash_flow()

    # Extração das métricas vitais direto da fonte contábil oficial
    lucro_liquido  = _extrair_dado_yq(dre, "NetIncome")
    ebit           = _extrair_dado_yq(dre, "EBIT")
    
    patrimonio_liq = _extrair_dado_yq(balanco, "StockholdersEquity")
    divida_total   = _extrair_dado_yq(balanco, "TotalDebt")
    caixa_eq       = _extrair_dado_yq(balanco, "CashAndCashEquivalents")
    
    caixa_livre    = _extrair_dado_yq(caixa, "FreeCashFlow")
    fco            = _extrair_dado_yq(caixa, "OperatingCashFlow")

    # Qtd de Ações e Dividendos
    num_acoes      = price_data.get('sharesOutstanding') or summary.get('averageDailyVolume10Day') or 1
    dividend_yield = summary.get('dividendYield') or summary.get('trailingAnnualDividendYield') or 0
    dividendo_anual = round(preco * dividend_yield, 2) if dividend_yield else 0

    # 3. RECÁLCULO DOS MÚLTIPLOS
    # Para evitar anomalias do provedor, sempre calculamos P/L e P/VP localmente com a DRE
    lpa = lucro_liquido / num_acoes if num_acoes > 0 else 0
    vpa = patrimonio_liq / num_acoes if num_acoes > 0 else 0
    
    pl_calculado  = preco / lpa if lpa > 0 else 0
    pvp_calculado = preco / vpa if vpa > 0 else 0
    
    # Informações de Setor
    perfil = ativo.asset_profile.get(ticker_formatado, {}) if isinstance(ativo.asset_profile, dict) else {}

    resultado = {
        "ticker":           ticker_upper,
        "nome":             price_data.get('longName') or price_data.get('shortName') or ticker_upper,
        "setor":            perfil.get('sector') or summary.get('sector') or '',
        "industria":        perfil.get('industry') or summary.get('industry') or '',
        "preco_atual":      preco,
        "lpa":              round(lpa, 2),
        "vpa":              round(vpa, 2),
        "pl":               round(pl_calculado, 2),
        "pvp":              round(pvp_calculado, 2),
        "dividendo_anual":  dividendo_anual,
        "dividend_yield":   round(dividend_yield * 100, 2),
        "fluxo_caixa":      caixa_livre,
        "fco_recente":      fco,
        "num_acoes":        num_acoes,
        "divida_liquida":   divida_total - caixa_eq,
        "ebit_12m":         ebit,
        "lucro_liquido_recente": lucro_liquido,
        "roe":              round((lucro_liquido / patrimonio_liq) * 100, 2) if patrimonio_liq > 0 else 0,
    }

    _cache[ticker_upper] = {
        "dados":     resultado,
        "timestamp": time.time(),
    }

    return resultado