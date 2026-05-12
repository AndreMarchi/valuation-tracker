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


def buscar_dados_acao_yf(ticker: str) -> dict:
    ticker_upper = ticker.upper().strip()

    if _cache_valido(ticker_upper):
        return _cache[ticker_upper]["dados"]

    # Tenta até 3 vezes com delay crescente
    tentativas = 3
    for tentativa in range(tentativas):
        try:
            ticker_formatado = _formatar_ticker_b3(ticker_upper)
            ativo = yf.Ticker(ticker_formatado)
            info  = ativo.info

            if not info or (info.get('regularMarketPrice') is None
                            and info.get('currentPrice') is None):
                raise ValueError(f"Ticker '{ticker}' não encontrado")

            preco           = info.get('currentPrice') or info.get('regularMarketPrice') or 0
            dividend_yield  = info.get('dividendYield') or 0
            dividendo_anual = round(preco * dividend_yield, 2) if dividend_yield else 0

            resultado = {
                "ticker":           ticker_upper,
                "nome":             info.get('longName') or info.get('shortName') or '',
                "setor":            info.get('sector') or '',
                "industria":        info.get('industry') or '',
                "preco_atual":      preco,
                "lpa":              info.get('trailingEps') or 0,
                "vpa":              info.get('bookValue') or 0,
                "pl":               info.get('trailingPE') or 0,
                "pvp":              info.get('priceToBook') or 0,
                "dividendo_anual":  dividendo_anual,
                "dividend_yield":   round(dividend_yield * 100, 2),
                "fluxo_caixa":      info.get('freeCashflow') or 0,
                "num_acoes":        info.get('sharesOutstanding') or 0,
                "roe":              round((info.get('returnOnEquity') or 0) * 100, 2),
                "divida_ebitda":    round(info.get('enterpriseToEbitda') or 0, 2),
                "margem_lucro":     round((info.get('profitMargins') or 0) * 100, 2),
            }

            # Log de debug temporário
            print(f"DEBUG {ticker_upper}:")
            print(f"  fluxo_caixa:   {resultado['fluxo_caixa']}")
            print(f"  num_acoes:     {resultado['num_acoes']}")
            print(f"  fcl_milhoes:   {resultado['fluxo_caixa'] / 1_000_000:.2f}")
            print(f"  acoes_milhoes: {resultado['num_acoes'] / 1_000_000:.2f}")

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
                    espera = (tentativa + 1) * 10  # 10s, 20s
                    print(f"Rate limit — aguardando {espera}s...")
                    time.sleep(espera)
                    continue
            raise

    raise Exception("Rate limit do yfinance — tente novamente em alguns minutos")