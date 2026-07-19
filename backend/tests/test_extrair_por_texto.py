"""
test_extrair_por_texto.py
Testes de dados/cvm_provider.py::extrair_por_texto() e da integração de
CAPEX/captação/amortização de dívida em buscar_inputs_fcfe_cvm().

Cobre especificamente os casos de falso-positivo encontrados na validação
manual contra 20 tickers (documentada no CONTEXT.md) — dividendo,
arrendamento, M&A, juros-só e custo de transação contaminando os filtros —
e o bug mais sério: a mesma posição de CD_CONTA representando contas
DIFERENTES em filings distintos da mesma empresa (confirmado em
TAEE3/Minerva), que fazia extrair_por_texto() misturar séries que não
deveriam ser somadas juntas.
"""

import pandas as pd
import pytest
from unittest.mock import patch

from dados.cvm_provider import (
    extrair_por_texto,
    calcular_ttm_por_texto,
    buscar_inputs_fcfe_cvm,
    _magnitude_convencao_fcfe,
    CAPEX_PREFIXO,
    PADRAO_CAPEX_INCLUIR,
    PADRAO_CAPEX_EXCLUIR,
    FINANCIAMENTO_PREFIXO,
    PADRAO_CAPTACAO_INCLUIR,
    PADRAO_CAPTACAO_EXCLUIR,
    PADRAO_AMORTIZACAO_INCLUIR,
    PADRAO_AMORTIZACAO_EXCLUIR,
    CONTA_LUCRO_LIQUIDO,
    CONTA_DEPRECIACAO_AMORTIZACAO,
    CONTA_VARIACAO_ATIVOS_PASSIVOS,
)


COLUNAS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC",
    "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]


def _linha(cd_conta, ds_conta, valor, dt_ini, dt_fim, ordem="ÚLTIMO", escala="MIL"):
    return {
        "CNPJ_CIA": "00.000.000/0001-00", "DT_REFER": dt_fim, "VERSAO": "1",
        "DENOM_CIA": "EMPRESA TESTE S.A.", "CD_CVM": "999999",
        "GRUPO_DFP": "DF Consolidado", "MOEDA": "REAL", "ESCALA_MOEDA": escala,
        "ORDEM_EXERC": ordem, "DT_INI_EXERC": dt_ini, "DT_FIM_EXERC": dt_fim,
        "CD_CONTA": cd_conta, "DS_CONTA": ds_conta, "VL_CONTA": str(valor),
        "ST_CONTA_FIXA": "N",
    }


def _df(linhas):
    return pd.DataFrame(linhas, columns=COLUNAS)


# ─── extrair_por_texto() — mecânica básica ──────────────────────────────────

class TestExtrairPorTextoMecanica:

    def test_filtra_por_prefixo_e_exige_linha_folha(self):
        df = _df([
            _linha("6.02", "Caixa Líquido Atividades de Investimento", "-999", "2025-01-01", "2025-03-31"),  # total do grupo, não é folha
            _linha("6.02.01", "Aquisição de imobilizado", "-100", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, "6.02", ["imobiliz"])
        assert len(serie) == 1
        assert serie.iloc[0] == -100_000.0  # só a linha-folha, não o total do grupo

    def test_inclusao_case_insensitive_e_sem_acento(self):
        df = _df([
            _linha("6.02.01", "AQUISIÇÃO DE INTANGÍVEL", "-50", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, "6.02", ["intangiv"])
        assert len(serie) == 1

    def test_serie_vazia_quando_nada_bate(self):
        df = _df([
            _linha("6.02.01", "Aquisição de investimentos", "-100", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, "6.02", ["imobiliz", "intangiv"])
        assert serie.empty

    def test_soma_multiplas_linhas_no_mesmo_periodo(self):
        df = _df([
            _linha("6.02.01", "Aquisição de imobilizado", "-100", "2025-01-01", "2025-03-31"),
            _linha("6.02.02", "Aquisição de intangível", "-30", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, "6.02", ["imobiliz", "intangiv"])
        assert len(serie) == 1
        assert serie.iloc[0] == -130_000.0

    def test_exclusao_derruba_linha_mesmo_batendo_inclusao(self):
        df = _df([
            _linha("6.02.01", "Aquisição de imobilizado", "-100", "2025-01-01", "2025-03-31"),
            _linha("6.02.02", "Venda de ativo imobilizado", "50", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, "6.02", ["imobiliz"], ["venda"])
        assert len(serie) == 1
        assert serie.iloc[0] == -100_000.0  # só a aquisição, a venda foi excluída

    def test_lookahead_exige_duas_palavras_independente_da_ordem(self):
        padrao = [r"(?=.*captac)(?=.*emprest)"]
        df = _df([
            _linha("6.03.01", "Captação de Empréstimos", "100", "2025-01-01", "2025-03-31"),
            _linha("6.03.02", "Captação de Debêntures", "50", "2025-01-01", "2025-03-31"),  # não tem "emprest"
        ])
        serie = extrair_por_texto(df, "6.03", padrao)
        assert len(serie) == 1
        assert serie.iloc[0] == 100_000.0  # só a linha com as duas palavras

    def test_dedup_trimestre_vs_acumulado_dentro_do_filtro(self):
        df = _df([
            _linha("6.02.01", "Aquisição de imobilizado", "-100", "2025-07-01", "2025-09-30"),  # trimestre isolado
            _linha("6.02.01", "Aquisição de imobilizado", "-250", "2025-01-01", "2025-09-30"),  # acumulado (deve ser ignorado)
        ])
        serie = extrair_por_texto(df, "6.02", ["imobiliz"])
        assert len(serie) == 1
        assert serie.iloc[0] == -100_000.0

    def test_nao_mistura_contas_diferentes_que_compartilham_cd_conta_em_anos_diferentes(self):
        # Bug real encontrado na validação (TAEE3): "6.03.03" é "Emissão de
        # debêntures" (captação) num filing e "Pagamento de Débentures -
        # Principal" (amortização) noutro. extrair_por_texto() não pode
        # herdar a linha errada só porque o código numérico colidiu.
        df = _df([
            _linha("6.03.03", "Emissão de debêntures, líquido de custos de transação sobre empréstimos", "500", "2023-01-01", "2023-03-31"),
            _linha("6.03.03", "Pagamento de Debêntures - Principal", "-300", "2024-01-01", "2024-03-31"),
        ])
        # filtro de amortização não deve pegar o valor de emissão (500)
        # que por acaso está no mesmo CD_CONTA em outro ano.
        serie_amort = extrair_por_texto(df, "6.03", PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)
        assert list(serie_amort.values) == [-300_000.0]  # só o pagamento, não a soma com a emissão

        # filtro de captação não deve pegar o pagamento de principal (-300)
        serie_capt = extrair_por_texto(df, "6.03", PADRAO_CAPTACAO_INCLUIR)
        assert list(serie_capt.values) == [500_000.0]  # só a emissão


# ─── falsos-positivos conhecidos (padrões reais do módulo) ──────────────────

class TestFalsosPositivosConhecidos:

    def test_capex_exclui_ma_mesmo_contendo_aquisicao(self):
        # Caso real CSED3: "Aquisição Grupo Veritas..." não é capex orgânico.
        df = _df([
            _linha("6.02.01", "Aquisição de imobilizado", "-50", "2025-01-01", "2025-03-31"),
            _linha("6.02.02", "Aquisição Grupo Veritas, líquido de caixa adquirido", "-9000", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, CAPEX_PREFIXO, PADRAO_CAPEX_INCLUIR, PADRAO_CAPEX_EXCLUIR)
        assert serie.iloc[0] == -50_000.0  # M&A não entrou

    def test_capex_exclui_venda_de_ativo(self):
        df = _df([
            _linha("6.02.01", "Aquisição de imobilizado", "-50", "2025-01-01", "2025-03-31"),
            _linha("6.02.02", "Venda de ativo imobilizado", "20", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, CAPEX_PREFIXO, PADRAO_CAPEX_INCLUIR, PADRAO_CAPEX_EXCLUIR)
        assert serie.iloc[0] == -50_000.0

    def test_captacao_exclui_custo_de_captacao(self):
        # Caso real B3SA3: "Custo de Captação de Debêntures" é despesa de
        # transação, não o principal captado.
        df = _df([
            _linha("6.03.01", "Custo de Captação de Debêntures", "-200", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, FINANCIAMENTO_PREFIXO, PADRAO_CAPTACAO_INCLUIR, PADRAO_CAPTACAO_EXCLUIR)
        assert serie.empty

    def test_captacao_mantem_linha_com_custo_como_qualificador(self):
        # Caso real RENT3: "líquido dos custos de captação" É a linha
        # certa de captação — só não pode excluir tudo que contém "custo".
        df = _df([
            _linha("6.03.01", "Empréstimos, financiamentos e títulos de dívida - Captações, líquido dos custos de captação", "700", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, FINANCIAMENTO_PREFIXO, PADRAO_CAPTACAO_INCLUIR, PADRAO_CAPTACAO_EXCLUIR)
        assert serie.iloc[0] == 700_000.0

    def test_amortizacao_exclui_dividendo(self):
        df = _df([
            _linha("6.03.01", "Pagamento de empréstimos e financiamentos", "-400", "2025-01-01", "2025-03-31"),
            _linha("6.03.02", "Pagamento de dividendos", "-1000", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, FINANCIAMENTO_PREFIXO, PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)
        assert serie.iloc[0] == -400_000.0  # dividendo não entrou

    def test_amortizacao_exclui_arrendamento(self):
        df = _df([
            _linha("6.03.01", "Pagamento de empréstimos e financiamentos", "-400", "2025-01-01", "2025-03-31"),
            _linha("6.03.02", "Pagamento de arrendamento", "-150", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, FINANCIAMENTO_PREFIXO, PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)
        assert serie.iloc[0] == -400_000.0

    def test_amortizacao_exclui_linha_so_de_juros(self):
        # Juros já está embutido no lucro líquido via resultado financeiro
        # — somar a linha de juros aqui dobraria a conta.
        df = _df([
            _linha("6.03.01", "Pagamento de principal - empréstimos", "-400", "2025-01-01", "2025-03-31"),
            _linha("6.03.02", "Pagamento de juros sobre empréstimos", "-80", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, FINANCIAMENTO_PREFIXO, PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)
        assert serie.iloc[0] == -400_000.0  # só o principal

    def test_amortizacao_mantem_linha_combinada_principal_e_juros(self):
        # Caso real CSED3: "Pagamento de principal e juros sobre
        # empréstimos e financiamentos" é a ÚNICA linha reportada — a
        # exclusão de juros não pode derrubar essa também.
        df = _df([
            _linha("6.03.01", "Pagamento de principal e juros sobre empréstimos e financiamentos", "-500", "2025-01-01", "2025-03-31"),
        ])
        serie = extrair_por_texto(df, FINANCIAMENTO_PREFIXO, PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)
        assert serie.iloc[0] == -500_000.0

    def test_amortizacao_pega_fraseado_liquidado_da_minerva(self):
        # Caso real BEEF3: a Minerva usa "liquidados", não
        # "pagamento"/"amortização" — sem esse padrão a série ficava vazia.
        df = _df([
            _linha("6.03.02", "Empréstimos e financiamentos liquidados", "-4207536", "2025-07-01", "2025-09-30"),
        ])
        serie = extrair_por_texto(df, FINANCIAMENTO_PREFIXO, PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)
        assert not serie.empty
        assert serie.iloc[0] == -4_207_536_000.0


# ─── _magnitude_convencao_fcfe() ─────────────────────────────────────────────

class TestMagnitudeConvencaoFcfe:

    def test_inverte_saida_negativa_para_magnitude_positiva(self):
        assert _magnitude_convencao_fcfe(-500.0) == 500.0

    def test_none_permanece_none(self):
        assert _magnitude_convencao_fcfe(None) is None

    def test_zero_permanece_zero(self):
        assert _magnitude_convencao_fcfe(0.0) == 0.0


# ─── buscar_inputs_fcfe_cvm() — integração completa ─────────────────────────

class TestBuscarInputsFcfeCvmComTextoIntegrado:

    def _mock_carregar_demo(self, dre_itr, dfc_itr, dre_dfp=None, dfc_dfp=None):
        vazio = _df([])
        dre_dfp = dre_dfp if dre_dfp is not None else vazio
        dfc_dfp = dfc_dfp if dfc_dfp is not None else vazio
        def _side_effect(tipo, cd_cvm):
            return {
                "itr_dre": dre_itr, "itr_dfc": dfc_itr,
                "dfp_dre": dre_dfp, "dfp_dfc": dfc_dfp,
            }.get(tipo, vazio)
        return _side_effect

    def _dre_4_trimestres(self, valor=100_000):
        periodos = [("2025-01-01","2025-03-31"),("2025-04-01","2025-06-30"),("2025-07-01","2025-09-30"),("2025-10-01","2025-12-31")]
        return _df([_linha(CONTA_LUCRO_LIQUIDO, "Lucro", valor, ini, fim) for ini, fim in periodos])

    def _dfc_completo(self, dep=1_000, var=-500, capex=-2_000, capt=3_000, amort=-2_500):
        periodos = [("2025-01-01","2025-03-31"),("2025-04-01","2025-06-30"),("2025-07-01","2025-09-30"),("2025-10-01","2025-12-31")]
        linhas = []
        for ini, fim in periodos:
            linhas.append(_linha(CONTA_DEPRECIACAO_AMORTIZACAO, "Depreciação", dep, ini, fim))
            linhas.append(_linha(CONTA_VARIACAO_ATIVOS_PASSIVOS, "Variações nos Ativos e Passivos", var, ini, fim))
            linhas.append(_linha("6.02.01", "Aquisição de imobilizado", capex, ini, fim))
            linhas.append(_linha("6.03.01", "Captação de empréstimos e financiamentos", capt, ini, fim))
            linhas.append(_linha("6.03.02", "Pagamento de empréstimos e financiamentos - principal", amort, ini, fim))
        return _df(linhas)

    def test_fcfe_completo_disponivel_quando_tudo_presente(self):
        dre = self._dre_4_trimestres()
        dfc = self._dfc_completo()
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre, dfc)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        assert r["fcfe_completo_disponivel"] is True
        assert r["capex"] == pytest.approx(2_000_000 * 4)       # magnitude positiva
        assert r["novas_dividas_emitidas"] == pytest.approx(3_000_000 * 4)  # já positivo, sem inversão
        assert r["amortizacao_dividas"] == pytest.approx(2_500_000 * 4)  # magnitude positiva

        # dict pronto pra alimentar calcular_fcfe() diretamente
        from valuation.fcfe import calcular_fcfe
        campos = {k: r[k] for k in ("lucro_liquido", "capex", "depreciacao", "delta_ccl", "novas_dividas_emitidas", "amortizacao_dividas")}
        resultado = calcular_fcfe(**campos)
        assert resultado.fcfe is not None

    def test_captacao_negativa_vira_none_nao_valor_errado(self):
        # Caso real WIZC3: a própria empresa reporta a linha de captação
        # com valor negativo no CSV bruto — não pode virar
        # "novas_dividas_emitidas" negativo.
        dre = self._dre_4_trimestres()
        dfc = self._dfc_completo(capt=-1_000)  # captação negativa (inconsistência de dado real)
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre, dfc)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["novas_dividas_emitidas"] is None
        assert r["fcfe_completo_disponivel"] is False

    def test_campos_de_texto_ausentes_ficam_none_sem_quebrar(self):
        dre = self._dre_4_trimestres()
        dfc_sem_texto = _df([
            _linha(CONTA_DEPRECIACAO_AMORTIZACAO, "Depreciação", -100, "2025-01-01", "2025-03-31"),
            _linha(CONTA_VARIACAO_ATIVOS_PASSIVOS, "Variações nos Ativos e Passivos", 10, "2025-01-01", "2025-03-31"),
        ])
        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre, dfc_sem_texto)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        assert r["capex"] is None
        assert r["novas_dividas_emitidas"] is None
        assert r["amortizacao_dividas"] is None
        assert r["fcfe_completo_disponivel"] is False


# ─── casos de sucesso mapeados (Minerva / CSED3) via calcular_ttm_por_texto ─

class TestCasosDeSucessoMapeados:

    def test_minerva_capex_e_amortizacao_com_fraseado_real(self):
        periodos = [("2025-01-01","2025-03-31"),("2025-04-01","2025-06-30"),("2025-07-01","2025-09-30"),("2025-10-01","2025-12-31")]
        linhas = []
        for ini, fim in periodos:
            linhas.append(_linha("6.02.02", "Aquisição de intangível, líquido", -2_000, ini, fim))
            linhas.append(_linha("6.02.03", "Aquisição de imobilizado, líquido", -275_568, ini, fim))
            linhas.append(_linha("6.03.01", "Empréstimos e financiamentos tomados", 865_601, ini, fim))
            linhas.append(_linha("6.03.02", "Empréstimos e financiamentos liquidados", -4_207_536, ini, fim))
        dfc = _df(linhas)
        vazio = _df([])

        capex = calcular_ttm_por_texto(dfc, vazio, CAPEX_PREFIXO, PADRAO_CAPEX_INCLUIR, PADRAO_CAPEX_EXCLUIR)
        capt  = calcular_ttm_por_texto(dfc, vazio, FINANCIAMENTO_PREFIXO, PADRAO_CAPTACAO_INCLUIR, PADRAO_CAPTACAO_EXCLUIR)
        amort = calcular_ttm_por_texto(dfc, vazio, FINANCIAMENTO_PREFIXO, PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)

        assert capex["valor"] == pytest.approx((-2_000 - 275_568) * 1000 * 4)
        assert capt["valor"] == pytest.approx(865_601 * 1000 * 4)
        assert amort["valor"] == pytest.approx(-4_207_536 * 1000 * 4)

    def test_csed3_captacao_multipla_linha_e_amortizacao_combinada(self):
        periodos = [("2025-01-01","2025-03-31"),("2025-04-01","2025-06-30"),("2025-07-01","2025-09-30"),("2025-10-01","2025-12-31")]
        linhas = []
        for ini, fim in periodos:
            linhas.append(_linha("6.03.03", "Captação de empréstimos e financiamentos", 200_000, ini, fim))
            linhas.append(_linha("6.03.06", "Captação de debêntures", 100_000, ini, fim))
            linhas.append(_linha("6.03.02", "Pagamento de principal e juros sobre empréstimos e financiamentos", -80_000, ini, fim))
        dfc = _df(linhas)
        vazio = _df([])

        capt  = calcular_ttm_por_texto(dfc, vazio, FINANCIAMENTO_PREFIXO, PADRAO_CAPTACAO_INCLUIR, PADRAO_CAPTACAO_EXCLUIR)
        amort = calcular_ttm_por_texto(dfc, vazio, FINANCIAMENTO_PREFIXO, PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)

        assert capt["valor"] == pytest.approx((200_000 + 100_000) * 1000 * 4)  # soma as duas linhas de captação
        assert amort["valor"] == pytest.approx(-80_000 * 1000 * 4)  # mantém a linha combinada principal+juros
