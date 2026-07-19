"""
test_trabalhador.py
Testes do worker de varredura em massa. Todos os testes usam mocks —
nenhum bate em rede de verdade.
"""

import pytest
from unittest.mock import patch, MagicMock

from scanner import trabalhador


# ─── _classificar_perfil_setor ──────────────────────────────────────────────

def test_perfil_banco_e_renda_longo_prazo():
    assert trabalhador._classificar_perfil_setor("Bancos") == "Renda / Longo Prazo"


def test_perfil_tecnologia_e_crescimento_ciclico():
    assert trabalhador._classificar_perfil_setor("Tecnologia") == "Crescimento / Cíclico"


def test_perfil_setor_sem_mapeamento_e_misto():
    assert trabalhador._classificar_perfil_setor("Setor Inexistente XYZ") == "Misto"


# ─── _linha_bulk_valida ──────────────────────────────────────────────────────

def test_linha_bulk_invalida_quando_none():
    assert trabalhador._linha_bulk_valida(None) is False


def test_linha_bulk_invalida_quando_preco_zerado():
    linha_mock = {"cotacao": 0, "pl": 5.0}
    assert trabalhador._linha_bulk_valida(linha_mock) is False


def test_linha_bulk_valida_quando_dados_ok():
    linha_mock = {"cotacao": 30.0, "pl": 8.0}
    assert trabalhador._linha_bulk_valida(linha_mock) is True


# ─── _mapear_linha_bulk ──────────────────────────────────────────────────────

def test_mapear_linha_bulk_deriva_lpa_vpa_e_num_acoes():
    linha_mock = {
        "cotacao": 30.0, "pl": 10.0, "pvp": 2.0, "dy": 0.05, "roe": 0.18,
        "mrgliq": 0.12, "c5y": 0.08, "liq2m": 1_000_000.0, "patrliq": 500_000_000.0,
    }
    cadastro = {"TESTE3": {"nome": "Teste S.A.", "setor": "Geral", "subsetor": "Geral"}}

    resultado = trabalhador._mapear_linha_bulk("TESTE3", linha_mock, cadastro)

    assert resultado["lpa"] == 3.0  # 30 / 10
    assert resultado["vpa"] == 15.0  # 30 / 2
    assert resultado["num_acoes"] == pytest.approx(500_000_000.0 / 15.0, abs=0.01)
    assert resultado["dividend_yield"] == 5.0  # 0.05 * 100
    assert resultado["roe"] == 18.0  # 0.18 * 100
    assert resultado["ebit_12m"] == 0.0
    assert resultado["div_liquida"] == 0.0
    assert resultado["nome"] == "Teste S.A."


# ─── lock de concorrência ────────────────────────────────────────────────────

def test_executar_scan_ignora_chamada_concorrente():
    """Se o lock já estiver preso, uma segunda chamada deve retornar sem rodar."""
    trabalhador._lock.acquire()
    try:
        with patch("scanner.trabalhador._carregar_tickers_representativos") as mock_tickers:
            trabalhador.executar_scan()
            mock_tickers.assert_not_called()
    finally:
        trabalhador._lock.release()


def test_scan_em_andamento_reflete_flag():
    assert trabalhador.scan_em_andamento() is False


# ─── escrita atômica do snapshot ─────────────────────────────────────────────

def test_escrever_snapshot_atomico_usa_replace(tmp_path, monkeypatch):
    caminho_falso = tmp_path / "snapshot_mercado.json"
    monkeypatch.setattr(trabalhador, "CAMINHO_SNAPSHOT", str(caminho_falso))

    payload = {"data_atualizacao": "2026-07-17T00:00:00", "setores": []}
    trabalhador._escrever_snapshot_atomico(payload)

    assert caminho_falso.exists()
    assert not (tmp_path / "snapshot_mercado.json.tmp").exists()


# ─── avaliar_ticker: fallback bulk -> individual ─────────────────────────────

def test_avaliar_ticker_usa_individual_quando_bulk_invalido():
    """Se a linha do bulk vier inválida, deve cair para buscar_dados()."""
    with patch("scanner.trabalhador.buscar_dados") as mock_buscar, \
         patch("scanner.trabalhador.buscar_saude_financeira_cvm", return_value={"disponivel": False}), \
         patch("scanner.trabalhador.buscar_selic_atual", return_value=0.145):

        mock_buscar.return_value = {
            "ticker": "TESTE3", "nome": "Empresa Teste", "setor": "Geral",
            "industria": "Geral", "preco_atual": 20.0, "lpa": 2.0, "vpa": 15.0,
            "pl": 10.0, "pvp": 1.3, "dividendo_anual": 1.0, "dividend_yield": 5.0,
            "fluxo_caixa": 100_000_000, "num_acoes": 10_000_000, "roe": 12.0,
            "divida_ebitda": 1.0, "margem_lucro": 10.0, "crescimento_receita_5a": 0.05,
            "ebit_12m": 50_000_000, "div_liquida": 20_000_000, "beta": 1.0,
        }

        resultado = trabalhador.avaliar_ticker("TESTE3", linha_bulk=None)

        mock_buscar.assert_called_once_with("TESTE3")
        assert resultado["fonte"] == "individual"
        assert resultado["ticker"] == "TESTE3"
        assert "score_atratividade" in resultado


def test_avaliar_ticker_usa_bulk_quando_valido():
    """Se a linha do bulk vier válida, não deve chamar buscar_dados()."""
    linha_mock = {
        "cotacao": 30.0, "pl": 10.0, "pvp": 2.0, "dy": 0.05, "roe": 0.18,
        "mrgliq": 0.12, "c5y": 0.08, "liq2m": 1_000_000.0, "patrliq": 500_000_000.0,
    }
    cadastro = {"TESTE3": {"nome": "Teste S.A.", "setor": "Geral", "subsetor": "Geral"}}

    with patch("scanner.trabalhador.buscar_dados") as mock_buscar, \
         patch("scanner.trabalhador.buscar_saude_financeira_cvm", return_value={"disponivel": False}), \
         patch("scanner.trabalhador.buscar_selic_atual", return_value=0.145):

        resultado = trabalhador.avaliar_ticker("TESTE3", linha_bulk=linha_mock, cadastro=cadastro)

        mock_buscar.assert_not_called()
        assert resultado["fonte"] == "bulk_fundamentus"
        assert resultado["ticker"] == "TESTE3"
