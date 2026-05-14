import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from dados.fundamentus_provider import buscar_dados_acao_fundamentus


def make_mock_df():
    """Cria mock do DataFrame retornado pelo Fundamentus."""
    return pd.DataFrame([{
        'Papel':              'PETR4',
        'Empresa':            'PETROBRAS PN',
        'Setor':              'Petróleo, Gás e Biocombustíveis',
        'Subsetor':           'Exploração, Refino e Distribuição',
        'Cotacao':            46.43,
        'Div_Yield':          '6.8%',
        'LPA':                835,
        'VPA':                3454,
        'PL':                 556,
        'PVP':                134,
        'Nro_Acoes':          12888700000,
        'Patrim_Liq':         445189000000,
        'Lucro_Liquido_12m':  107583000000,
        'EBIT_12m':           194617000000,
        'Div_Liquida':        324091000000,
        'ROE':                '24.2%',
        'Marg_Liquida':       '21.7%',
    }], index=['PETR4'])


def test_retorna_campos_obrigatorios():
    """Todos os campos necessários devem estar presentes."""
    with patch("dados.fundamentus_provider.fundamentus.get_papel", return_value=make_mock_df()):
        resultado = buscar_dados_acao_fundamentus("PETR4")

    campos = ["ticker", "nome", "preco_atual", "lpa", "vpa",
              "pl", "pvp", "dividendo_anual", "fluxo_caixa", "num_acoes"]
    for campo in campos:
        assert campo in resultado, f"Campo '{campo}' não encontrado"


def test_preco_correto():
    with patch("dados.fundamentus_provider.fundamentus.get_papel", return_value=make_mock_df()):
        resultado = buscar_dados_acao_fundamentus("PETR4")
    assert resultado["preco_atual"] == 46.43


def test_lpa_correto():
    with patch("dados.fundamentus_provider.fundamentus.get_papel", return_value=make_mock_df()):
        resultado = buscar_dados_acao_fundamentus("PETR4")
    assert resultado["lpa"] == 8.35


def test_dividendo_calculado():
    """Dividendo anual = preço × yield."""
    with patch("dados.fundamentus_provider.fundamentus.get_papel", return_value=make_mock_df()):
        resultado = buscar_dados_acao_fundamentus("PETR4")
    esperado = round(46.43 * 0.068, 2)
    assert resultado["dividendo_anual"] == esperado


def test_ticker_invalido():
    with patch("dados.fundamentus_provider.fundamentus.get_papel", side_effect=Exception("not found")):
        with pytest.raises(ValueError, match="não encontrado"):
            buscar_dados_acao_fundamentus("XYZINVALIDO")


def test_ticker_maiusculo():
    with patch("dados.fundamentus_provider.fundamentus.get_papel", return_value=make_mock_df()):
        resultado = buscar_dados_acao_fundamentus("petr4")
    assert resultado["ticker"] == "PETR4"