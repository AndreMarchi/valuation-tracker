import time
from dados.fundamentus_provider import buscar_dados_acao_fundamentus
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
    1. Fundamentus — mais rápido e rico para B3
    2. Brapi — fallback com token
    3. yfinance — último recurso
    """

    ticker_upper = ticker.upper().strip()

    if _cache_valido(ticker_upper):
        print(f"Cache hit: {ticker_upper}")
        return _cache[ticker_upper]["dados"]

    erros = []

    # 1. Fundamentus
    try:
        print(f"Tentando Fundamentus para {ticker_upper}...")
        resultado = buscar_dados_acao_fundamentus(ticker_upper)
        fonte = "fundamentus"
    except Exception as e:
        erros.append(f"Fundamentus: {e}")
        print(f"Fundamentus falhou — tentando Brapi...")

        # 2. Brapi
        try:
            resultado = buscar_dados_acao_sync(ticker_upper)
            fonte = "brapi"
        except Exception as e2:
            erros.append(f"Brapi: {e2}")
            print(f"Brapi falhou — tentando yfinance...")

            # 3. yfinance
            try:
                resultado = buscar_dados_acao_yf(ticker_upper)
                fonte = "yfinance"
            except Exception as e3:
                erros.append(f"yfinance: {e3}")
                raise Exception(f"Todas as fontes falharam: {' | '.join(erros)}")

    resultado["fonte"] = fonte
    _cache[ticker_upper] = {
        "dados":     resultado,
        "timestamp": time.time(),
    }
    print(f"✅ Dados obtidos via {fonte} para {ticker_upper}")
    return resultado