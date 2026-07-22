import os
import time
import json
import math
from yahooquery import Ticker

# Importações dos provedores restantes
from dados.fundamentus_provider import buscar_dados_acao_fundamentus
from dados.yquery_provider import buscar_dados_acao_yq
from dados.yfinance_provider import buscar_dados_acao_yf
from dados.normalizacao_setor import normalizar_setor

# Variáveis globais para otimização
_cache: dict = {}
_TICKERS_CACHE = []
CACHE_DURACAO_SEGUNDOS = 600

def _cache_valido(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    return (time.time() - _cache[ticker]["timestamp"]) < CACHE_DURACAO_SEGUNDOS

def _buscar_risco_complementar(ticker: str, preco_atual: float, num_acoes: float) -> dict:
    ticker_formatado = f"{ticker.upper().strip()}.SA"
    try:
        ativo = Ticker(ticker_formatado)
        summary = ativo.summary_detail.get(ticker_formatado, {})
        price_data = ativo.price.get(ticker_formatado, {})
        
        # beta=None sinaliza "dado genuinamente ausente/indisponível" — só
        # main.py/scanner/trabalhador.py sabem se devem usar um fallback
        # setorial (BETA_POR_SETOR) ou o 1.0 genérico antigo. Nunca inventar
        # um "1.0 real" aqui, senão fica indistinguível de um beta que a
        # fonte realmente reportou como 1.0 (ver CONTEXT.md).
        if isinstance(summary, str) or isinstance(price_data, str):
            return {"beta": None, "valor_mercado": 0.0}

        beta_ativo = summary.get('beta') or summary.get('fiveYearBeta')
        if beta_ativo is None or math.isnan(beta_ativo):
            beta_ativo = None

        valor_mercado = price_data.get('marketCap') or summary.get('marketCap')
        if not valor_mercado and num_acoes > 0 and preco_atual > 0:
            valor_mercado = preco_atual * num_acoes
        elif not valor_mercado:
            valor_mercado = 0.0

        beta_final = round(float(beta_ativo), 2) if beta_ativo is not None else None
        return {"beta": beta_final, "valor_mercado": float(valor_mercado)}
    except Exception as e:
        print(f"⚠️ Aviso: Falha ao buscar risco complementar para {ticker}: {e}")
        return {"beta": None, "valor_mercado": 0.0}

def buscar_dados(ticker: str) -> dict:
    ticker_upper = ticker.upper().strip()
    if _cache_valido(ticker_upper):
        return _cache[ticker_upper]["dados"]

    erros = []
    # 1. Fundamentus (Agora é a prioridade #1)
    try:
        print(f"Tentando Fundamentus para {ticker_upper}...")
        resultado = buscar_dados_acao_fundamentus(ticker_upper)
        fonte = "fundamentus"
    except Exception as e1:
        erros.append(f"Fundamentus: {e1}")
        # 2. YahooQuery
        try:
            resultado = buscar_dados_acao_yq(ticker_upper)
            fonte = "yahooquery"
        except Exception as e2:
            erros.append(f"YahooQuery: {e2}")
            # 3. Yfinance
            try:
                resultado = buscar_dados_acao_yf(ticker_upper)
                fonte = "yfinance"
            except Exception as e3:
                erros.append(f"yfinance: {e3}")
                raise Exception(f"Todas as fontes falharam: {' | '.join(erros)}")

    # Complemento de risco
    if fonte not in ["yahooquery", "yfinance"]:
        dados_comp = _buscar_risco_complementar(ticker_upper, resultado.get("preco_atual", 0.0), resultado.get("num_acoes", 1.0))
        resultado["beta"] = dados_comp["beta"]
        resultado["valor_mercado"] = dados_comp["valor_mercado"]
    
    # Normaliza a string de setor UMA vez aqui — ponto único usado por todo
    # o resto do pipeline (main.py, scanner/trabalhador.py), pra não ter
    # cada consumidor comparando contra sua própria lista de strings soltas
    # (ver dados/normalizacao_setor.py e CONTEXT.md pro mismatch real
    # encontrado: "Alimentos Processados"/"Comércio" não batiam com as
    # chaves "Alimentos"/"Varejo" usadas em CAPM/NOPAT/crescimento/ciclicos).
    resultado["setor"] = normalizar_setor(resultado.get("setor", ""))

    resultado["fonte"] = fonte
    _cache[ticker_upper] = {"dados": resultado, "timestamp": time.time()}
    return resultado

def carregar_todos_tickers_b3():
    """Lê o JSON de setores uma única vez (em memória)."""
    global _TICKERS_CACHE
    if _TICKERS_CACHE:
        return _TICKERS_CACHE
        
    caminho_json = os.path.join("dados", "setores_b3.json")
    if os.path.exists(caminho_json):
        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            _TICKERS_CACHE = [item["Tickets"] for item in dados if item.get("Tickets")]
    return _TICKERS_CACHE