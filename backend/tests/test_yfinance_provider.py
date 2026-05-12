import pytest
from unittest.mock import patch, MagicMock
from dados.yfinance_provider import buscar_dados_acao_yf, _formatar_ticker_b3

MOCK_YF_INFO = {
    "longName":          "Petroleo Brasileiro SA Pfd",
    "currentPrice":      48.66,
    "trailingEps":       8.58,
    "bookValue":         32.39,
    "trailingPE":        6.23,
    "priceToBook":       1.50,
    "dividendYield":     0.05,
    "freeCashflow":      94680000000,
    "sharesOutstanding": 12888733000,
    "returnOnEquity":    0.26,
    "profitMargins":     0.22,
    "enterpriseToEbitda":5.44,
    "sector":            "Energy",
    "industry":          "Oil & Gas Integrated",
}


def make_mock_ticker(info_data):
    """Cria mock do objeto yf.Ticker."""
    mock_ticker = MagicMock()
    mock_ticker.info = info_data
    return mock_ticker


def test_formatar_ticker_sem_sa():
    """Deve adicionar .SA ao ticker brasileiro."""
    assert _formatar_ticker_b3("PETR4") == "PETR4.SA"


def test_formatar_ticker_com_sa():
    """Não deve duplicar .SA se já existir."""
    assert _formatar_ticker_b3("PETR4.SA") == "PETR4.SA"


def test_formatar_ticker_lowercase():
    """Deve converter para maiúsculas."""
    assert _formatar_ticker_b3("petr4") == "PETR4.SA"


def test_buscar_dados_retorna_campos_obrigatorios():
    """Todos os campos necessários devem estar presentes."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("PETR4")

    campos = ["ticker", "nome", "preco_atual", "lpa", "vpa",
              "pl", "pvp", "dividendo_anual", "fluxo_caixa", "num_acoes"]
    for campo in campos:
        assert campo in resultado, f"Campo '{campo}' não encontrado"


def test_buscar_dados_lpa_correto():
    """LPA deve ser mapeado corretamente."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("PETR4")
    assert resultado["lpa"] == 8.58


def test_buscar_dados_dividendo_calculado():
    """Dividendo anual deve ser calculado como yield × preço."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("PETR4")
    esperado = round(48.66 * 0.05, 2)
    assert resultado["dividendo_anual"] == esperado


def test_ticker_invalido_lanca_excecao():
    """Ticker inválido deve lançar ValueError."""
    mock_info = {"regularMarketPrice": None, "currentPrice": None}
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(mock_info)):
        with pytest.raises(ValueError, match="não encontrado"):
            buscar_dados_acao_yf("XYZINVALIDO")


def test_ticker_maiusculo_no_resultado():
    """Ticker no resultado deve estar em maiúsculas sem .SA."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("petr4")
    assert resultado["ticker"] == "PETR4"