"""
test_liquidacao_cvm_inputs.py
Testes de integração da coleta de Ativos/Passivo via CVM
(dados/cvm_provider.py::buscar_ativos_para_liquidacao_cvm), que alimenta o
Valor de Liquidação (valuation puro já coberto em test_valor_liquidacao.py).

Mesmo padrão de mock de test_fcfe_cvm_inputs.py: DataFrames sintéticos no
lugar dos CSVs reais de BPA/BPP, via patch de _carregar_demo/buscar_cd_cvm.
"""

import pandas as pd
import pytest
from unittest.mock import patch

from dados.cvm_provider import (
    buscar_ativos_para_liquidacao_cvm,
    CONTA_ATIVO_TOTAL,
    CONTA_CAIXA_EQUIVALENTES,
    CONTA_APLICACOES_FINANCEIRAS_CIRCULANTE,
    CONTA_CONTAS_A_RECEBER_CIRCULANTE,
    CONTA_ESTOQUES,
    CONTA_IMOBILIZADO,
    CONTA_INTANGIVEL,
    CONTA_PASSIVO_CIRCULANTE,
    CONTA_PASSIVO_NAO_CIRCULANTE,
)

COLUNAS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_FIM_EXERC",
    "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]


def _linha(cd_conta, ds_conta, valor, dt_fim="2026-03-31", ordem="ÚLTIMO", escala="MIL"):
    return {
        "CNPJ_CIA": "00.000.000/0001-00",
        "DT_REFER": dt_fim,
        "VERSAO": "1",
        "DENOM_CIA": "EMPRESA TESTE S.A.",
        "CD_CVM": "999999",
        "GRUPO_DFP": "DF Consolidado",
        "MOEDA": "REAL",
        "ESCALA_MOEDA": escala,
        "ORDEM_EXERC": ordem,
        "DT_FIM_EXERC": dt_fim,
        "CD_CONTA": cd_conta,
        "DS_CONTA": ds_conta,
        "VL_CONTA": str(valor),
        "ST_CONTA_FIXA": "S",
    }


def _df_bpa(caixa, aplicacoes, receber, estoques, imobilizado, intangivel, ativo_total):
    linhas = [
        _linha(CONTA_ATIVO_TOTAL, "Ativo Total", ativo_total),
        _linha(CONTA_CAIXA_EQUIVALENTES, "Caixa e Equivalentes de Caixa", caixa),
        _linha(CONTA_APLICACOES_FINANCEIRAS_CIRCULANTE, "Aplicações Financeiras", aplicacoes),
        _linha(CONTA_CONTAS_A_RECEBER_CIRCULANTE, "Contas a Receber", receber),
        _linha(CONTA_ESTOQUES, "Estoques", estoques),
        _linha(CONTA_IMOBILIZADO, "Imobilizado", imobilizado),
        _linha(CONTA_INTANGIVEL, "Intangível", intangivel),
    ]
    return pd.DataFrame(linhas, columns=COLUNAS)


def _df_bpp(passivo_circulante, passivo_nao_circulante):
    linhas = [
        _linha(CONTA_PASSIVO_CIRCULANTE, "Passivo Circulante", passivo_circulante),
        _linha(CONTA_PASSIVO_NAO_CIRCULANTE, "Passivo Não Circulante", passivo_nao_circulante),
    ]
    return pd.DataFrame(linhas, columns=COLUNAS)


def _vazio():
    return pd.DataFrame(columns=COLUNAS)


class TestBuscarAtivosParaLiquidacaoCvm:

    def _mock_carregar_demo(self, bpa, bpp):
        def _side_effect(tipo, cd_cvm):
            if tipo == "itr_bpa":
                return bpa
            if tipo == "itr_bpp":
                return bpp
            return _vazio()  # dfp_* vazio (não usado se itr já tem dado)
        return _side_effect

    def test_dados_completos_extrai_todas_as_classes_com_escala_mil_aplicada(self):
        bpa = _df_bpa(
            caixa=1000, aplicacoes=500, receber=2000, estoques=1500,
            imobilizado=4000, intangivel=1000, ativo_total=9000,
        )
        bpp = _df_bpp(passivo_circulante=2000, passivo_nao_circulante=1000)

        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(bpa, bpp)):
            r = buscar_ativos_para_liquidacao_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        # ESCALA_MOEDA="MIL" -> multiplica por 1000
        assert r["caixa_equivalentes"] == pytest.approx(1_000_000.0)
        assert r["aplicacoes_financeiras"] == pytest.approx(500_000.0)
        assert r["contas_a_receber"] == pytest.approx(2_000_000.0)
        assert r["estoques"] == pytest.approx(1_500_000.0)
        assert r["imobilizado"] == pytest.approx(4_000_000.0)
        assert r["intangivel"] == pytest.approx(1_000_000.0)
        assert r["ativo_total_bpa"] == pytest.approx(9_000_000.0)
        assert r["passivo_total"] == pytest.approx(3_000_000.0)  # 2000+1000, x1000

    def test_empresa_nao_encontrada_retorna_disponivel_false(self):
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=None):
            r = buscar_ativos_para_liquidacao_cvm("TEST3", "EMPRESA INEXISTENTE")
        assert r["disponivel"] is False
        assert "erro" in r

    def test_bpa_vazio_retorna_disponivel_false_sem_quebrar(self):
        bpp = _df_bpp(passivo_circulante=2000, passivo_nao_circulante=1000)
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(_vazio(), bpp)):
            r = buscar_ativos_para_liquidacao_cvm("TEST3", "EMPRESA TESTE S.A.")
        assert r["disponivel"] is False

    def test_bpp_vazio_retorna_disponivel_false_sem_quebrar(self):
        bpa = _df_bpa(1000, 500, 2000, 1500, 4000, 1000, 9000)
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(bpa, _vazio())):
            r = buscar_ativos_para_liquidacao_cvm("TEST3", "EMPRESA TESTE S.A.")
        assert r["disponivel"] is False

    def test_ativo_e_passivo_totais_zerados_retorna_disponivel_false(self):
        """Mesmo sintoma real já documentado em
        buscar_capital_investido_proxy_cvm() (ex: GEPA4) — BPA/BPP inteiros
        zerados na fonte não pode virar um valor de liquidação de R$0,00
        (enganoso: parece 'sem ativos nem passivos', não 'dado ausente')."""
        bpa = _df_bpa(0, 0, 0, 0, 0, 0, ativo_total=0)
        bpp = _df_bpp(passivo_circulante=0, passivo_nao_circulante=0)
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(bpa, bpp)):
            r = buscar_ativos_para_liquidacao_cvm("TEST3", "EMPRESA TESTE S.A.")
        assert r["disponivel"] is False

    def test_classe_ausente_no_bpa_vira_zero_nao_quebra(self):
        """Uma conta que não bate (ex: empresa sem Aplicações Financeiras
        reportadas) tem que virar 0.0 (ausência real de saldo), não None
        nem exceção — mesmo padrão de _ultimo_valor() já usado em
        buscar_capital_investido_proxy_cvm()."""
        linhas = [
            _linha(CONTA_ATIVO_TOTAL, "Ativo Total", 5000),
            _linha(CONTA_CAIXA_EQUIVALENTES, "Caixa e Equivalentes de Caixa", 1000),
            # sem aplicações financeiras, contas a receber, estoques, imobilizado, intangível
        ]
        bpa = pd.DataFrame(linhas, columns=COLUNAS)
        bpp = _df_bpp(passivo_circulante=1000, passivo_nao_circulante=500)

        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(bpa, bpp)):
            r = buscar_ativos_para_liquidacao_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        assert r["caixa_equivalentes"] == pytest.approx(1_000_000.0)
        assert r["aplicacoes_financeiras"] == pytest.approx(0.0)
        assert r["contas_a_receber"] == pytest.approx(0.0)
        assert r["estoques"] == pytest.approx(0.0)
        assert r["imobilizado"] == pytest.approx(0.0)
        assert r["intangivel"] == pytest.approx(0.0)
