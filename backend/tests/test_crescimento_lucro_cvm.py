"""
test_crescimento_lucro_cvm.py
Testes de dados/cvm_provider.py::buscar_crescimento_lucro_anual_cvm() — CAGR
de lucro líquido anual via CVM, criado pra substituir o crescimento de
RECEITA que main.py usava por engano pra projetar o LPA (lucro por ação)
no DCF Duas Fases (valuation/crescimento.py::calcular_dcf_duas_fases()).

Achado real que motivou a correção (Status Invest): CAGR de Receita 5a da
Minerva/BEEF3 = +23,09%, CAGR de Lucro 5a = +0,42% — usar o de receita pra
projetar lucro inflava o valor justo dramaticamente. Ver CONTEXT.md.

Segue a mesma convenção de mock do resto da suíte (test_ttm_correto.py,
test_fcfe_cvm_inputs.py): mocka `_carregar_demo`, não bate na rede.
"""

import pandas as pd
import pytest
from unittest.mock import patch

from dados.cvm_provider import buscar_crescimento_lucro_anual_cvm, CONTA_LUCRO_LIQUIDO


COLUNAS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC",
    "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]


def _linha_anual(valor, ano, ordem="ÚLTIMO"):
    return {
        "CNPJ_CIA": "00.000.000/0001-00", "DT_REFER": f"{ano}-12-31", "VERSAO": "1",
        "DENOM_CIA": "EMPRESA TESTE S.A.", "CD_CVM": "999999",
        "GRUPO_DFP": "DF Consolidado", "MOEDA": "REAL", "ESCALA_MOEDA": "MIL",
        "ORDEM_EXERC": ordem, "DT_INI_EXERC": f"{ano}-01-01", "DT_FIM_EXERC": f"{ano}-12-31",
        "CD_CONTA": CONTA_LUCRO_LIQUIDO, "DS_CONTA": "Lucro Líquido", "VL_CONTA": str(valor),
        "ST_CONTA_FIXA": "S",
    }


def _df(linhas):
    return pd.DataFrame(linhas, columns=COLUNAS)


def _mock_carregar_demo(dfp_dre):
    vazio = _df([])
    def _side_effect(tipo, cd_cvm):
        return dfp_dre if tipo == "dfp_dre" else vazio
    return _side_effect


class TestBuscarCrescimentoLucroAnualCvm:

    def test_empresa_com_prejuizo_no_meio_do_periodo_fica_indisponivel(self):
        # Réplica do caso real da BEEF3: FY2023 lucro, FY2024 PREJUÍZO, FY2025 lucro.
        dfp = _df([
            _linha_anual(395533, 2023),
            _linha_anual(-1563806, 2024),
            _linha_anual(848260, 2025),
        ])
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=_mock_carregar_demo(dfp)):
            r = buscar_crescimento_lucro_anual_cvm("BEEF3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is False
        assert "Prejuízo" in r["erro"]
        # não inventa um CAGR mesmo tendo os dados — não deve ter a chave 'cagr'
        assert "cagr" not in r

    def test_empresa_com_lucro_positivo_todo_periodo_calcula_cagr_real(self):
        # Réplica do caso real da WEGE3: lucro crescendo de forma consistente.
        dfp = _df([
            _linha_anual(5867615, 2023),
            _linha_anual(6318763, 2024),
            _linha_anual(6775958, 2025),
        ])
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=_mock_carregar_demo(dfp)):
            r = buscar_crescimento_lucro_anual_cvm("WEGE3", "WEG S.A.")

        assert r["disponivel"] is True
        # CAGR 2 anos: (6775958/5867615)^(1/2) - 1 ≈ 0,0746
        assert r["cagr"] == pytest.approx(0.0746, abs=0.001)
        assert r["anos_considerados"] == [2023, 2024, 2025]

    def test_cagr_e_clampado_na_faixa_conservadora(self):
        # Crescimento absurdo (10x em 1 ano) deve ser clampado a 30%, não
        # propagado cru pra uma projeção de 5 anos.
        dfp = _df([
            _linha_anual(100, 2024),
            _linha_anual(1000, 2025),
        ])
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=_mock_carregar_demo(dfp)):
            r = buscar_crescimento_lucro_anual_cvm("XYZW3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        assert r["cagr"] == pytest.approx(0.30)

    def test_menos_de_2_exercicios_fica_indisponivel(self):
        dfp = _df([_linha_anual(100, 2025)])
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=_mock_carregar_demo(dfp)):
            r = buscar_crescimento_lucro_anual_cvm("XYZW3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is False

    def test_empresa_nao_encontrada_na_cvm(self):
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=None):
            r = buscar_crescimento_lucro_anual_cvm("XYZW3", "EMPRESA INEXISTENTE")

        assert r["disponivel"] is False
        assert "não encontrada" in r["erro"]

    def test_dfp_vazio_fica_indisponivel_sem_quebrar(self):
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", return_value=_df([])):
            r = buscar_crescimento_lucro_anual_cvm("XYZW3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is False
