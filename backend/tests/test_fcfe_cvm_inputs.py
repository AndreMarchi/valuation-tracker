"""
test_fcfe_cvm_inputs.py
Testes de integração da coleta de inputs de FCFE via CVM
(dados/cvm_provider.py::buscar_inputs_fcfe_cvm), incluindo a extração da
conta 6.01.02 via _extrair_serie() e a inversão de sinal de ΔCCL.

Não testa valuation/fcfe.py em si (funções puras, já cobertas em
test_fcfe.py) — só o pipeline que alimenta essas funções com dados reais
da CVM.
"""

import pandas as pd
import pytest
from unittest.mock import patch

from dados.cvm_provider import (
    buscar_inputs_fcfe_cvm,
    _delta_ccl_convencao_academica,
    _extrair_serie,
    CONTA_VARIACAO_ATIVOS_PASSIVOS,
)


# ─── helpers ────────────────────────────────────────────────────────────────

COLUNAS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC",
    "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]


def _linha(cd_conta, ds_conta, valor, dt_ini, dt_fim, ordem="ÚLTIMO", escala="MIL"):
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
        "DT_INI_EXERC": dt_ini,
        "DT_FIM_EXERC": dt_fim,
        "CD_CONTA": cd_conta,
        "DS_CONTA": ds_conta,
        "VL_CONTA": str(valor),
        "ST_CONTA_FIXA": "S",
    }


def _df_dfc_4_trimestres(valores_variacao, valores_depreciacao):
    """DFC sintético com 4 trimestres isolados (sem duplicata YTD) para
    6.01.01.02 (depreciação) e 6.01.02 (variação de ativos/passivos)."""
    periodos = [
        ("2025-01-01", "2025-03-31"),
        ("2025-04-01", "2025-06-30"),
        ("2025-07-01", "2025-09-30"),
        ("2025-10-01", "2025-12-31"),
    ]
    linhas = []
    for (ini, fim), v_var, v_dep in zip(periodos, valores_variacao, valores_depreciacao):
        linhas.append(_linha("6.01.02", "Variações nos Ativos e Passivos", v_var, ini, fim))
        linhas.append(_linha("6.01.01.02", "Depreciações e amortizações", v_dep, ini, fim))
    return pd.DataFrame(linhas, columns=COLUNAS)


def _df_dre_4_trimestres(valores_lucro):
    periodos = [
        ("2025-01-01", "2025-03-31"),
        ("2025-04-01", "2025-06-30"),
        ("2025-07-01", "2025-09-30"),
        ("2025-10-01", "2025-12-31"),
    ]
    linhas = [
        _linha("3.11", "Lucro/Prejuízo Consolidado do Período", v, ini, fim)
        for (ini, fim), v in zip(periodos, valores_lucro)
    ]
    return pd.DataFrame(linhas, columns=COLUNAS)


# ─── _extrair_serie() aplicada à conta 6.01.02 ───────────────────────────────

class TestExtracaoVariacaoAtivosPassivos:

    def test_extrai_valor_correto_em_reais_com_fator_mil(self):
        df = pd.DataFrame([
            _linha("6.01.02", "Variações nos Ativos e Passivos", "-500", "2025-01-01", "2025-03-31"),
        ], columns=COLUNAS)
        serie = _extrair_serie(df, CONTA_VARIACAO_ATIVOS_PASSIVOS)
        assert len(serie) == 1
        assert serie.iloc[0] == -500_000.0  # ESCALA_MOEDA=MIL -> x1000

    def test_ignora_linha_acumulada_ytd_duplicada(self):
        # Mesmo DT_FIM_EXERC reportado como trimestre isolado (jul-set) E
        # como acumulado no exercício (jan-set) — comportamento real do ITR
        # já documentado no CONTEXT.md para outras contas (3.01, 3.11 etc).
        # _extrair_serie deve ficar só com o trimestre isolado (menor duração).
        df = pd.DataFrame([
            _linha("6.01.02", "Variações nos Ativos e Passivos", "-300", "2025-07-01", "2025-09-30"),  # trimestre isolado
            _linha("6.01.02", "Variações nos Ativos e Passivos", "-950", "2025-01-01", "2025-09-30"),  # acumulado
        ], columns=COLUNAS)
        serie = _extrair_serie(df, CONTA_VARIACAO_ATIVOS_PASSIVOS)
        assert len(serie) == 1
        assert serie.iloc[0] == -300_000.0  # só o trimestre isolado, não a soma dos dois

    def test_ignora_duplicata_exata_entre_penultimo_e_ultimo(self):
        # Mesmo valor reportado 2x pro mesmo período (ÚLTIMO na própria
        # janela + PENÚLTIMO comparativo num filing posterior) não pode
        # ser somado em dobro.
        df = pd.DataFrame([
            _linha("6.01.02", "Variações nos Ativos e Passivos", "200", "2025-01-01", "2025-03-31", ordem="ÚLTIMO"),
            _linha("6.01.02", "Variações nos Ativos e Passivos", "200", "2025-01-01", "2025-03-31", ordem="PENÚLTIMO"),
        ], columns=COLUNAS)
        serie = _extrair_serie(df, CONTA_VARIACAO_ATIVOS_PASSIVOS)
        assert len(serie) == 1
        assert serie.iloc[0] == 200_000.0

    def test_conta_ausente_retorna_serie_vazia(self):
        df = pd.DataFrame([
            _linha("6.01.01", "Caixa Gerado nas Operações", "100", "2025-01-01", "2025-03-31"),
        ], columns=COLUNAS)
        serie = _extrair_serie(df, CONTA_VARIACAO_ATIVOS_PASSIVOS)
        assert serie.empty


# ─── _delta_ccl_convencao_academica() — inversão de sinal isolada ──────────

class TestInversaoSinalDeltaCcl:

    def test_positivo_vira_negativo(self):
        # Conta CVM +100 (impacto em caixa: liberou caixa) deve virar
        # delta_ccl -100 (convenção acadêmica: capital de giro caiu).
        assert _delta_ccl_convencao_academica(100) == -100

    def test_negativo_vira_positivo(self):
        # Conta CVM -50 (consumiu caixa) deve virar delta_ccl +50
        # (capital de giro aumentou).
        assert _delta_ccl_convencao_academica(-50) == 50

    def test_zero_permanece_zero(self):
        assert _delta_ccl_convencao_academica(0) == 0

    def test_e_involutiva(self):
        # Aplicar a inversão duas vezes deve devolver o valor original —
        # confirma que é uma troca de sinal simples, não uma fórmula com
        # outros termos escondidos.
        valor = 12345.67
        assert _delta_ccl_convencao_academica(_delta_ccl_convencao_academica(valor)) == valor


# ─── buscar_inputs_fcfe_cvm() — pipeline completo, mockado ──────────────────

class TestBuscarInputsFcfeCvm:

    def _mock_carregar_demo(self, dre, dfc):
        def _side_effect(tipo, cd_cvm):
            if tipo == "itr_dre":
                return dre
            if tipo == "itr_dfc":
                return dfc
            return pd.DataFrame(columns=COLUNAS)  # dfp_* vazio (não usado se itr já tem dado)
        return _side_effect

    def test_dados_completos_exceto_capex_e_financiamento(self):
        dre = _df_dre_4_trimestres([100_000, 110_000, 120_000, 130_000])
        dfc = _df_dfc_4_trimestres(
            valores_variacao=[-10_000, -20_000, 5_000, -15_000],
            valores_depreciacao=[5_000, 5_500, 6_000, 6_200],
        )
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre, dfc)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        assert r["lucro_liquido"] == pytest.approx(460_000_000.0)  # soma TTM x1000
        assert r["depreciacao"] == pytest.approx(22_700_000.0)
        assert r["capex"] is None
        assert r["novas_dividas_emitidas"] is None
        assert r["amortizacao_dividas"] is None
        assert r["fcfe_completo_disponivel"] is False

    def test_sinal_delta_ccl_no_pipeline_completo(self):
        # Soma TTM da conta CVM 6.01.02 = -10000-20000+5000-15000 = -40000
        # (x1000 pela ESCALA_MOEDA) = -40_000_000 em reais, convenção CVM.
        # delta_ccl esperado (convenção acadêmica) = +40_000_000 — sinal
        # trocado, valor sintético óbvio pra deixar a decisão auditável.
        dre = _df_dre_4_trimestres([100_000, 100_000, 100_000, 100_000])
        dfc = _df_dfc_4_trimestres(
            valores_variacao=[-10_000, -20_000, 5_000, -15_000],
            valores_depreciacao=[1_000, 1_000, 1_000, 1_000],
        )
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre, dfc)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["delta_ccl"] == pytest.approx(40_000_000.0)
        assert r["delta_ccl"] > 0  # convenção acadêmica: capital de giro cresceu, consumiu caixa

    def test_capex_novas_dividas_amortizacao_sao_none_explicito_nao_zero(self):
        dre = _df_dre_4_trimestres([100_000] * 4)
        dfc = _df_dfc_4_trimestres([0] * 4, [0] * 4)
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre, dfc)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        for campo in ("capex", "novas_dividas_emitidas", "amortizacao_dividas"):
            assert campo in r
            assert r[campo] is None, f"{campo} deveria ser None (dado indisponível), não um valor"

    def test_menos_de_4_trimestres_retorna_none_sem_quebrar(self):
        dre = _df_dre_4_trimestres([100_000] * 4).iloc[:2]  # só 2 trimestres
        dfc = _df_dfc_4_trimestres([0] * 4, [0] * 4).iloc[:4]
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre, dfc)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        assert r["lucro_liquido"] is None

    def test_empresa_nao_encontrada_na_cvm(self):
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=None):
            r = buscar_inputs_fcfe_cvm("XXXX3", "EMPRESA INEXISTENTE")

        assert r["disponivel"] is False
        assert "não encontrada" in r["erro"].lower()

    def test_demonstracoes_vazias_retorna_indisponivel(self):
        vazio = pd.DataFrame(columns=COLUNAS)
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", return_value=vazio):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is False
        assert "erro" in r

    def test_campos_do_dict_batem_com_parametros_de_calcular_fcfe(self):
        # As chaves precisam bater com os nomes de parâmetro de
        # valuation.fcfe.calcular_fcfe(), pra permitir calcular_fcfe(**inputs)
        # assim que capex/novas_dividas/amortizacao forem implementados.
        from valuation.fcfe import calcular_fcfe
        import inspect

        parametros_fcfe = set(inspect.signature(calcular_fcfe).parameters.keys())

        dre = _df_dre_4_trimestres([100_000] * 4)
        dfc = _df_dfc_4_trimestres([0] * 4, [0] * 4)
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre, dfc)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        campos_relevantes = parametros_fcfe & set(r.keys())
        assert campos_relevantes == parametros_fcfe, (
            f"Faltam chaves em buscar_inputs_fcfe_cvm() pra bater com calcular_fcfe(): "
            f"{parametros_fcfe - campos_relevantes}"
        )
