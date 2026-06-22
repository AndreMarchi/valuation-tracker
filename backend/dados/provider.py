import time
from dados.brapi import buscar_dados_acao_sync
from dados.fundamentus_provider import buscar_dados_acao_fundamentus
from dados.yquery_provider import buscar_dados_acao_yq
from dados.yfinance_provider import buscar_dados_acao_yf

# Usaremos o YahooQuery apenas para complementar os dados de risco rapidamente
from yahooquery import Ticker
import math

_cache: dict = {}
CACHE_DURACAO_SEGUNDOS = 600  # 10 minutos

def _cache_valido(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    return (time.time() - _cache[ticker]["timestamp"]) < CACHE_DURACAO_SEGUNDOS

def _buscar_risco_complementar(ticker: str, preco_atual: float, num_acoes: float) -> dict:
    """Busca cirurgicamente o Beta e o Valor de Mercado via YahooQuery caso o provedor principal não os tenha."""
    ticker_formatado = f"{ticker.upper().strip()}.SA"
    try:
        ativo = Ticker(ticker_formatado)
        summary = ativo.summary_detail.get(ticker_formatado, {})
        price_data = ativo.price.get(ticker_formatado, {})
        
        if isinstance(summary, str) or isinstance(price_data, str):
            return {"beta": 1.0, "valor_mercado": 0.0}

        beta_ativo = summary.get('beta') or summary.get('fiveYearBeta')
        if beta_ativo is None or math.isnan(beta_ativo):
            beta_ativo = 1.0

        valor_mercado = price_data.get('marketCap') or summary.get('marketCap')
        if not valor_mercado and num_acoes > 0 and preco_atual > 0:
            valor_mercado = preco_atual * num_acoes
        elif not valor_mercado:
            valor_mercado = 0.0

        return {
            "beta": round(float(beta_ativo), 2),
            "valor_mercado": float(valor_mercado)
        }
    except Exception as e:
        print(f"⚠️ Aviso: Falha ao buscar risco complementar para {ticker}: {e}")
        return {"beta": 1.0, "valor_mercado": 0.0}


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
    resultado = {}

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

    # ─── COSTURA CIRÚRGICA DE RISCO INSTITUCIONAL ───
    # Se a fonte não foi o Yahoo (onde já implementamos a coleta), busca as variáveis separadamente
    if fonte not in ["yahooquery", "yfinance"]:
        print(f"🔄 Complementando variáveis de risco (Beta) via YahooQuery...")
        preco_atual = resultado.get("preco_atual", 0.0)
        num_acoes = resultado.get("num_acoes", 1.0)
        
        dados_complementares = _buscar_risco_complementar(ticker_upper, preco_atual, num_acoes)
        
        # Injeta as variáveis diretamente no dicionário de resposta
        resultado["beta"] = dados_complementares["beta"]
        resultado["valor_mercado"] = dados_complementares["valor_mercado"]
    
    resultado["fonte"] = fonte
    
    # Salva no cache da memória RAM para não bombardear as APIs
    _cache[ticker_upper] = {
        "dados":     resultado,
        "timestamp": time.time(),
    }
    
    print(f"✅ Dados obtidos via {fonte} para {ticker_upper} (Beta: {resultado.get('beta')})")
    return resultado