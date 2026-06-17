import yfinance as yf
import time

_cache: dict = {}
CACHE_DURACAO_SEGUNDOS = 600  # 10 minutos

def _cache_valido(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    idade = time.time() - _cache[ticker]["timestamp"]
    return idade < CACHE_DURACAO_SEGUNDOS

def _formatar_ticker_b3(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if not ticker.endswith('.SA'):
        ticker = f"{ticker}.SA"
    return ticker

def _extrair_dado_seguro(df, linha: str) -> float:
    """Extrai o valor mais recente da linha do DataFrame, retornando 0 se falhar."""
    if df is None or df.empty:
        return 0.0
    try:
        # Pega o primeiro valor da linha solicitada (o ano/trimestre mais recente)
        if linha in df.index:
            valor = df.loc[linha].iloc[0]
            # Filtra valores NaN que o Pandas pode retornar
            import math
            if valor is None or math.isnan(valor):
                return 0.0
            return float(valor)
        return 0.0
    except Exception:
        return 0.0

def buscar_dados_acao_yf(ticker: str) -> dict:
    ticker_upper = ticker.upper().strip()

    if _cache_valido(ticker_upper):
        return _cache[ticker_upper]["dados"]

    tentativas = 3
    for tentativa in range(tentativas):
        try:
            ticker_formatado = _formatar_ticker_b3(ticker_upper)
            ativo = yf.Ticker(ticker_formatado)
            
            # O .info ainda é útil apenas para o preço atual em tempo real e setor
            info = ativo.info
            
            # Validação de existência
            if not info or (info.get('regularMarketPrice') is None and info.get('currentPrice') is None):
                # Se o info falhar, testa se pelo menos o histórico de preços existe
                hist = ativo.history(period="5d")
                if hist.empty:
                    raise ValueError(f"Ticker '{ticker}' não encontrado ou sem liquidez")
                preco = hist['Close'].iloc[-1]
            else:
                preco = info.get('currentPrice') or info.get('regularMarketPrice') or 0

            # ─── EXTRAÇÃO DOS BALANÇOS CONTÁBEIS REAIS ───────────────────────
            dre = ativo.financials         # Demonstração de Resultados
            balanco = ativo.balance_sheet  # Balanço Patrimonial
            caixa = ativo.cashflow         # Demonstração de Fluxo de Caixa

            # Extração Cirúrgica (Lendo direto da contabilidade, ignorando o .info)
            lucro_liquido  = _extrair_dado_seguro(dre, "Net Income")
            receita        = _extrair_dado_seguro(dre, "Total Revenue")
            ebit           = _extrair_dado_seguro(dre, "EBIT")
            
            patrimonio_liq = _extrair_dado_seguro(balanco, "Stockholders Equity")
            divida_total   = _extrair_dado_seguro(balanco, "Total Debt")
            caixa_livre    = _extrair_dado_seguro(caixa, "Free Cash Flow")
            fco            = _extrair_dado_seguro(caixa, "Operating Cash Flow")

            # Qtd de ações (O .info geralmente acerta isso, mas o balanço traz a média diluída)
            num_acoes = info.get('sharesOutstanding') or _extrair_dado_seguro(dre, "Diluted Average Shares") or 1

            # Recálculo dos múltiplos localmente para garantir precisão
            lpa = lucro_liquido / num_acoes if num_acoes > 0 else 0
            vpa = patrimonio_liq / num_acoes if num_acoes > 0 else 0
            
            pl_calculado  = preco / lpa if lpa > 0 else 0
            pvp_calculado = preco / vpa if vpa > 0 else 0
            
            # Dividendos
            dividend_yield = info.get('dividendYield') or 0
            dividendo_anual = round(preco * dividend_yield, 2) if dividend_yield else 0

            resultado = {
                "ticker":           ticker_upper,
                "nome":             info.get('longName') or info.get('shortName') or ticker_upper,
                "setor":            info.get('sector') or '',
                "industria":        info.get('industry') or '',
                "preco_atual":      preco,
                "lpa":              round(lpa, 2),
                "vpa":              round(vpa, 2),
                "pl":               round(pl_calculado, 2),
                "pvp":              round(pvp_calculado, 2),
                "dividendo_anual":  dividendo_anual,
                "dividend_yield":   round(dividend_yield * 100, 2),
                "fluxo_caixa":      caixa_livre,       # Substitui o info.get('freeCashflow') quebrado
                "fco_recente":      fco,               # Excelente para o Quality Score
                "num_acoes":        num_acoes,
                "divida_liquida":   divida_total - _extrair_dado_seguro(balanco, "Cash And Cash Equivalents"),
                "ebit_12m":         ebit,
                "lucro_liquido_recente": lucro_liquido,
                "roe":              round((lucro_liquido / patrimonio_liq) * 100, 2) if patrimonio_liq > 0 else 0,
            }

            _cache[ticker_upper] = {
                "dados":     resultado,
                "timestamp": time.time(),
            }

            return resultado

        except ValueError:
            raise
        except Exception as e:
            if "Rate" in str(e) or "429" in str(e):
                if tentativa < tentativas - 1:
                    espera = (tentativa + 1) * 10
                    print(f"Rate limit — aguardando {espera}s...")
                    time.sleep(espera)
                    continue
            raise

    raise Exception("Rate limit do yfinance — tente novamente em alguns minutos")