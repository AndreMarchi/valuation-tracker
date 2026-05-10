import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dados.brapi import buscar_dados_acao

MOCK_BRAPI_RESPONSE = {
    "results": [{
        "symbol": "PETR4",
        "longName": "Petroleo Brasileiro SA Pfd",
        "regularMarketPrice": 48.66,
        "priceEarnings": 5.69,
        "earningsPerShare": 8.58,
        "defaultKeyStatistics": {
            "trailingEps": 8.581526,
            "bookValue": 32.399384,
            "trailingPE": 6.2389836,
            "priceToBook": 1.5018804,
            "sharesOutstanding": 12888733000,
            "yield": 0.05,
            "dividendYield": 0.05,
            "enterpriseToEbitda": 5.44,
        },
        "financialData": {
            "freeCashflow": 94680000000,
            "returnOnEquity": 0.26486695,
            "profitMargins": 0.22229971,
        },
        "summaryProfile": {
            "sector": "Energia",
            "industry": "Petróleo e Gás Integrado",
        },
    }]
}


async def mock_get(*args, **kwargs):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=MOCK_BRAPI_RESPONSE)  # SEM AsyncMock
    return response


async def mock_get_empty(*args, **kwargs):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"results": []})  # SEM AsyncMock
    return response


@pytest.mark.asyncio
async def test_buscar_dados_retorna_campos_obrigatorios():
    with patch("dados.brapi.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = mock_get
        resultado = await buscar_dados_acao("PETR4")

    campos = ["ticker", "nome", "preco_atual", "lpa", "vpa",
              "pl", "pvp", "dividendo_anual", "fluxo_caixa", "num_acoes"]
    for campo in campos:
        assert campo in resultado, f"Campo '{campo}' não encontrado"


@pytest.mark.asyncio
async def test_buscar_dados_lpa_correto():
    with patch("dados.brapi.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = mock_get
        resultado = await buscar_dados_acao("PETR4")

    assert resultado["lpa"] == 8.581526


@pytest.mark.asyncio
async def test_buscar_dados_dividendo_calculado():
    with patch("dados.brapi.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = mock_get
        resultado = await buscar_dados_acao("PETR4")

    esperado = round(48.66 * 0.05, 2)
    assert resultado["dividendo_anual"] == esperado


@pytest.mark.asyncio
async def test_ticker_invalido_lanca_excecao():
    with patch("dados.brapi.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = mock_get_empty
        with pytest.raises(ValueError, match="não encontrado"):
            await buscar_dados_acao("XYZINVALIDO")