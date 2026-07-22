import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BRAPI_TOKEN = os.getenv("BRAPI_TOKEN")
BRAPI_URL   = "https://brapi.dev/api"


async def buscar_dados_acao(ticker: str) -> dict:
    url    = f"{BRAPI_URL}/quote/{ticker}"
    params = {
        "token":    BRAPI_TOKEN,
        "modules":  "summaryProfile,defaultKeyStatistics,financialData",
        "interval": "1d",
        "range":    "1mo",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

    if not data.get("results"):
        raise ValueError(f"Ticker '{ticker}' não encontrado na B3")

    r     = data["results"][0]
    stats = r.get("defaultKeyStatistics", {}) or {}
    fin   = r.get("financialData", {}) or {}

    preco          = r.get("regularMarketPrice", 0) or 0
    dividend_yield = stats.get("yield") or stats.get("dividendYield") or 0
    dividendo_anual = round(preco * dividend_yield, 2) if dividend_yield else 0

    # brapi não retorna patrimônio líquido absoluto, só bookValue (VPA —
    # patrimônio líquido POR AÇÃO). Reconstitui o absoluto multiplicando
    # por num_acoes — mesma lógica de vpa = patrim_liq/num_acoes usada nos
    # outros providers, só invertida.
    num_acoes = stats.get("sharesOutstanding") or 0
    vpa       = stats.get("bookValue") or 0
    patrim_liq = vpa * num_acoes if num_acoes > 0 else 0

    return {
        "ticker":           ticker.upper(),
        "nome":             r.get("longName", ""),
        "setor":            r.get("summaryProfile", {}).get("sector", ""),
        "industria":        r.get("summaryProfile", {}).get("industry", ""),
        "preco_atual":      preco,
        "lpa":              stats.get("trailingEps") or stats.get("earningsPerShare") or 0,
        "vpa":              vpa,
        "pl":               stats.get("trailingPE") or r.get("priceEarnings") or 0,
        "pvp":              stats.get("priceToBook") or 0,
        "dividendo_anual":  dividendo_anual,
        "dividend_yield":   round(dividend_yield * 100, 2),
        "fluxo_caixa":      fin.get("freeCashflow") or 0,
        "patrim_liq":       patrim_liq,
        "num_acoes":        num_acoes,
        "roe":              round((fin.get("returnOnEquity") or 0) * 100, 2),
        "divida_ebitda":    round(stats.get("enterpriseToEbitda") or 0, 2),
        "margem_lucro":     round((fin.get("profitMargins") or 0) * 100, 2),
    }


def buscar_dados_acao_sync(ticker: str) -> dict:
    """Versão síncrona — usada como fallback quando o yfinance falha."""
    url    = f"{BRAPI_URL}/quote/{ticker}"
    params = {
        "token":   BRAPI_TOKEN,
        "modules": "summaryProfile,defaultKeyStatistics,financialData",
    }

    response = httpx.get(url, params=params, timeout=10.0)
    response.raise_for_status()
    data = response.json()

    if not data.get("results"):
        raise ValueError(f"Ticker '{ticker}' não encontrado na B3")

    r     = data["results"][0]
    stats = r.get("defaultKeyStatistics", {}) or {}
    fin   = r.get("financialData", {}) or {}

    preco          = r.get("regularMarketPrice", 0) or 0
    dividend_yield = stats.get("yield") or stats.get("dividendYield") or 0
    dividendo_anual = round(preco * dividend_yield, 2) if dividend_yield else 0

    # brapi não retorna patrimônio líquido absoluto, só bookValue (VPA —
    # patrimônio líquido POR AÇÃO). Reconstitui o absoluto multiplicando
    # por num_acoes — mesma lógica de vpa = patrim_liq/num_acoes usada nos
    # outros providers, só invertida.
    num_acoes = stats.get("sharesOutstanding") or 0
    vpa       = stats.get("bookValue") or 0
    patrim_liq = vpa * num_acoes if num_acoes > 0 else 0

    return {
        "ticker":           ticker.upper(),
        "nome":             r.get("longName", ""),
        "setor":            r.get("summaryProfile", {}).get("sector", ""),
        "industria":        r.get("summaryProfile", {}).get("industry", ""),
        "preco_atual":      preco,
        "lpa":              stats.get("trailingEps") or stats.get("earningsPerShare") or 0,
        "vpa":              vpa,
        "pl":               stats.get("trailingPE") or r.get("priceEarnings") or 0,
        "pvp":              stats.get("priceToBook") or 0,
        "dividendo_anual":  dividendo_anual,
        "dividend_yield":   round(dividend_yield * 100, 2),
        "fluxo_caixa":      fin.get("freeCashflow") or 0,
        "patrim_liq":       patrim_liq,
        "num_acoes":        num_acoes,
        "roe":              round((fin.get("returnOnEquity") or 0) * 100, 2),
        "divida_ebitda":    round(stats.get("enterpriseToEbitda") or 0, 2),
        "margem_lucro":     round((fin.get("profitMargins") or 0) * 100, 2),
    }
