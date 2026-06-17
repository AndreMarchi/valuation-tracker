import time
from dados.brapi import buscar_dados_acao_sync
from dados.fundamentus_provider import buscar_dados_acao_fundamentus
from dados.yquery_provider import buscar_dados_acao_yq
from dados.yfinance_provider import buscar_dados_acao_yf

_cache: dict = {}
CACHE_DURACAO_SEGUNDOS = 600  # 10 minutos


def _cache_valido(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    return (time.time() - _cache[ticker]["timestamp"]) < CACHE_DURACAO_SEGUNDOS


def buscar_dados(ticker: str) -> dict:
    """
    Busca dados com fallback automático e cascata de segurança:
    1. Brapi — API oficial e estruturada focada no Brasil
    2. Fundamentus — Base de dados rica em múltiplos da B3
    3. YahooQuery — Acesso JSON direto e rápido aos balanços contábeis
    4. Yfinance — Último recurso em caso de falha sistêmica geral
    """

    ticker_upper = ticker.upper().strip()

    if _cache_valido(ticker_upper):
        print(f"Cache hit: {ticker_upper}")
        return _cache[ticker_upper]["dados"]

    erros = []

    # 1. Brapi
    try:
        print(f"Tentando Brapi para {ticker_upper}...")
        resultado = buscar_dados_acao_sync(ticker_upper)
        fonte = "brapi"
    except Exception as e1:
        erros.append(f"Brapi: {e1}")
        print(f"Brapi falhou — tentando Fundamentus...")

        # 2. Fundamentus
        try:
            resultado = buscar_dados_acao_fundamentus(ticker_upper)
            fonte = "fundamentus"
        except Exception as e2:
            erros.append(f"Fundamentus: {e2}")
            print(f"Fundamentus falhou — tentando YahooQuery...")

            # 3. YahooQuery (A nova âncora de segurança)
            try:
                resultado = buscar_dados_acao_yq(ticker_upper)
                fonte = "yahooquery"
            except Exception as e3:
                erros.append(f"YahooQuery: {e3}")
                print(f"YahooQuery falhou — tentando Yfinance...")

                # 4. Yfinance (O último recurso)
                try:
                    resultado = buscar_dados_acao_yf(ticker_upper)
                    fonte = "yfinance"
                except Exception as e4:
                    erros.append(f"yfinance: {e4}")
                    raise Exception(f"Todas as fontes de dados falharam: {' | '.join(erros)}")

    resultado["fonte"] = fonte
    
    # Salva no cache da memória RAM para não bombardear as APIs
    _cache[ticker_upper] = {
        "dados":     resultado,
        "timestamp": time.time(),
    }
    
    print(f"✅ Dados obtidos via {fonte} para {ticker_upper}")
    return resultado