import time
from dados.yfinance_provider import buscar_dados_acao_yf
from dados.brapi import buscar_dados_acao_sync


_cache: dict = {}
CACHE_DURACAO_SEGUNDOS = 600  # 10 minutos


def _cache_valido(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    return (time.time() - _cache[ticker]["timestamp"]) < CACHE_DURACAO_SEGUNDOS


def buscar_dados(ticker: str) -> dict:
    """
    Busca dados com fallback automático:
    1. Tenta yfinance (gratuito, sem token)
    2. Se falhar, usa Brapi como backup
    """

    ticker_upper = ticker.upper().strip()

    if _cache_valido(ticker_upper):
        print(f"Cache hit: {ticker_upper}")
        return _cache[ticker_upper]["dados"]

    # Tenta yfinance primeiro
    try:
        print(f"Tentando yfinance para {ticker_upper}...")
        resultado = buscar_dados_acao_yf(ticker_upper)
        fonte = "yfinance"
    except Exception as e:
        print(f"yfinance falhou ({e}) — tentando Brapi...")
        try:
            resultado = buscar_dados_acao_sync(ticker_upper)
            fonte = "brapi"
        except Exception as e2:
            raise Exception(f"Ambas as fontes falharam. yfinance: {e} | Brapi: {e2}")

    resultado["fonte"] = fonte
    _cache[ticker_upper] = {
        "dados":     resultado,
        "timestamp": time.time(),
    }
    print(f"Dados obtidos via {fonte} para {ticker_upper}")
    return resultado