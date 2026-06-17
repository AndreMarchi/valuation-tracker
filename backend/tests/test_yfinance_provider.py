import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from dados.yfinance_provider import buscar_dados_acao_yf, _formatar_ticker_b3

# O .info foi reduzido apenas ao que o novo código realmente consome
MOCK_YF_INFO = {
    "longName":          "Petroleo Brasileiro SA Pfd",
    "currentPrice":      48.66,
    "dividendYield":     0.05,
    "sharesOutstanding": 100,  # Reduzido para 100 para facilitar o cálculo mental dos testes
    "sector":            "Energy",
    "industry":          "Oil & Gas Integrated",
}


def make_mock_ticker(info_data, empty_history=False):
    """
    Cria mock do objeto yf.Ticker, injetando DataFrames do Pandas 
    para simular as demonstrações contábeis reais.
    """
    mock_ticker = MagicMock()
    mock_ticker.info = info_data
    
    # 1. Simulação do histórico de preços (Fallback de segurança)
    if empty_history:
        mock_ticker.history.return_value = pd.DataFrame()
    else:
        mock_ticker.history.return_value = pd.DataFrame({"Close": [48.66]})

    # 2. Simulação da Demonstração de Resultados (DRE)
    # Lucro de 858 dividido por 100 ações = LPA de 8.58
    mock_ticker.financials = pd.DataFrame(
        {
            "Net Income": [858.0], 
            "Total Revenue": [20000.0], 
            "EBIT": [1500.0],
            "Diluted Average Shares": [100.0]
        },
        index=["Net Income", "Total Revenue", "EBIT", "Diluted Average Shares"]
    )

    # 3. Simulação do Balanço Patrimonial
    # Patrimônio de 3239 dividido por 100 ações = VPA de 32.39
    mock_ticker.balance_sheet = pd.DataFrame(
        {
            "Stockholders Equity": [3239.0], 
            "Total Debt": [5000.0], 
            "Cash And Cash Equivalents": [1000.0]
        },
        index=["Stockholders Equity", "Total Debt", "Cash And Cash Equivalents"]
    )

    # 4. Simulação do Fluxo de Caixa
    mock_ticker.cashflow = pd.DataFrame(
        {
            "Free Cash Flow": [9468.0], 
            "Operating Cash Flow": [12000.0]
        },
        index=["Free Cash Flow", "Operating Cash Flow"]
    )

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
    """Todos os campos necessários devem estar presentes e extraídos corretamente."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("PETR4")

    campos = [
        "ticker", "nome", "preco_atual", "lpa", "vpa",
        "pl", "pvp", "dividendo_anual", "fluxo_caixa", "num_acoes", 
        "fco_recente", "divida_liquida", "ebit_12m", "lucro_liquido_recente"
    ]
    for campo in campos:
        assert campo in resultado, f"Campo '{campo}' não encontrado no retorno"


def test_buscar_dados_lpa_correto():
    """LPA deve ser calculado matematicamente: Net Income / Shares."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("PETR4")
    assert resultado["lpa"] == 8.58


def test_buscar_dados_vpa_correto():
    """VPA deve ser calculado matematicamente: Stockholders Equity / Shares."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("PETR4")
    assert resultado["vpa"] == 32.39


def test_buscar_dados_dividendo_calculado():
    """Dividendo anual deve ser calculado como yield × preço."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("PETR4")
    esperado = round(48.66 * 0.05, 2)
    assert resultado["dividendo_anual"] == esperado


def test_ticker_invalido_lanca_excecao():
    """Ticker inválido deve lançar ValueError, inclusive falhando no histórico de preços."""
    mock_info = {"regularMarketPrice": None, "currentPrice": None}
    
    # Adicionamos empty_history=True para garantir que o fallback de verificação de preço falhe
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(mock_info, empty_history=True)):
        with pytest.raises(ValueError, match="não encontrado"):
            buscar_dados_acao_yf("XYZINVALIDO")


def test_ticker_maiusculo_no_resultado():
    """Ticker no resultado deve estar em maiúsculas sem .SA."""
    with patch("dados.yfinance_provider.yf.Ticker", return_value=make_mock_ticker(MOCK_YF_INFO)):
        resultado = buscar_dados_acao_yf("petr4")
    assert resultado["ticker"] == "PETR4"