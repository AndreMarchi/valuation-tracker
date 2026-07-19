"""
test_dna_por_texto.py
Testes da extração de D&A (Depreciação/Amortização) por texto — prefixo
6.01.01.XX, ver DEPRECIACAO_PREFIXO/PADRAO_DEPRECIACAO_INCLUIR/EXCLUIR em
dados/cvm_provider.py.

Contexto do bug: a posição fixa CONTA_DEPRECIACAO_AMORTIZACAO ("6.01.01.02")
tem ST_CONTA_FIXA="S" (obrigatória de preencher), mas isso NÃO significa que
a mesma posição sempre representa o mesmo conceito contábil entre empresas —
confirmado por auditoria contra ~450 empresas reais (itr_dre_2025/itr_dfc_2025):
140/438 (32%) divergem, sem concentração setorial. Os textos reais abaixo
(DS_CONTA que a posição fixa continha, e o texto real da linha de D&A) foram
extraídos das próprias empresas durante essa auditoria — ver CONTEXT.md.
"""

import pandas as pd
import pytest

from dados.cvm_provider import (
    calcular_ttm_por_texto,
    DEPRECIACAO_PREFIXO,
    PADRAO_DEPRECIACAO_INCLUIR,
    PADRAO_DEPRECIACAO_EXCLUIR,
    CONTA_DEPRECIACAO_AMORTIZACAO,
)


COLUNAS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC",
    "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]


def _linha(cd_conta, ds_conta, valor, dt_ini, dt_fim, ordem="ÚLTIMO"):
    return {
        "CNPJ_CIA": "00.000.000/0001-00", "DT_REFER": dt_fim, "VERSAO": "1",
        "DENOM_CIA": "EMPRESA TESTE S.A.", "CD_CVM": "999999",
        "GRUPO_DFP": "DF Consolidado", "MOEDA": "REAL", "ESCALA_MOEDA": "MIL",
        "ORDEM_EXERC": ordem, "DT_INI_EXERC": dt_ini, "DT_FIM_EXERC": dt_fim,
        "CD_CONTA": cd_conta, "DS_CONTA": ds_conta, "VL_CONTA": str(valor),
        "ST_CONTA_FIXA": "S",
    }


def _df(linhas):
    return pd.DataFrame(linhas, columns=COLUNAS)


def _quatro_trimestres(cd_conta, ds_conta, valor):
    """4 trimestres isolados idênticos (ITR Q1-Q3 + Q4 já isolado) — evita
    depender da derivação de Q4 via DFP, que já é testada à parte em
    test_ttm_correto.py; aqui o foco é o casamento de texto."""
    periodos = [("2025-01-01", "2025-03-31"), ("2025-04-01", "2025-06-30"),
                ("2025-07-01", "2025-09-30"), ("2025-10-01", "2025-12-31")]
    return _df([_linha(cd_conta, ds_conta, valor, ini, fim) for ini, fim in periodos])


def _dna_por_texto(df):
    vazio = _df([])
    return calcular_ttm_por_texto(df, vazio, DEPRECIACAO_PREFIXO, PADRAO_DEPRECIACAO_INCLUIR, PADRAO_DEPRECIACAO_EXCLUIR)


# ─── casos já documentados: BBSE3, CXSE3, PSSA3 ────────────────────────────

class TestCasosDivergentesJaDocumentados:

    def test_bbse3_posicao_fixa_era_resultado_de_participacoes_agora_none(self):
        # BBSE3 real: a posição fixa 6.01.01.02 contém "Resultado de
        # investimentos em participações societárias" — nada a ver com D&A.
        # A seguradora não reporta nenhuma linha de depreciação/amortização
        # no bloco 6.01.01.XX -> deve ficar None, não usar a posição errada.
        df = _quatro_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, "Resultado de investimentos em participações societárias", -50_000)
        r = _dna_por_texto(df)
        assert r["valor"] is None

    def test_cxse3_posicao_fixa_era_resultado_de_participacoes_agora_none(self):
        df = _quatro_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, "Resultado de investimentos em operações societárias", -30_000)
        r = _dna_por_texto(df)
        assert r["valor"] is None

    def test_pssa3_posicao_fixa_era_ajustes_exercicios_anteriores_mas_tem_dna_real(self):
        # Porto Seguro (PSSA3) real: a posição fixa contém "Ajustes
        # exercícios anteriores" (errado), mas diferente de BBSE3/CXSE3 a
        # empresa TEM uma linha de D&A real em outra posição do bloco
        # (seguradora com operações diversificadas, tem imobilizado
        # relevante) -> deve achar o valor certo, não None e não o errado.
        df = pd.concat([
            _quatro_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, "Ajustes exercícios anteriores", 999_999),
            _quatro_trimestres("6.01.01.05", "Depreciação e amortização", 105_000),
        ], ignore_index=True)
        r = _dna_por_texto(df)
        assert r["valor"] == pytest.approx(105_000 * 1000 * 4)  # não usou os 999.999 da posição errada


# ─── 5 tickers "normais" divergentes da auditoria (sem tratamento setorial) ─

class TestTickersNormaisDivergentes:
    """
    Confirma que a correção funciona pra empresas industriais comuns, sem
    nenhum tratamento especial de setor — a divergência da posição fixa não
    é um problema só de bancos/seguradoras (ver CONTEXT.md: 140/438, sem
    concentração setorial).
    """

    def test_petrobras_posicao_fixa_era_encargos_financeiros(self):
        df = pd.concat([
            _quatro_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, "Encargos, Rendimentos Financeiros e Atualizações Monetárias e Cambiais", 5_000_000),
            _quatro_trimestres("6.01.01.04", "Depreciação, depleção e amortização", 18_976_000),
        ], ignore_index=True)
        r = _dna_por_texto(df)
        assert r["valor"] == pytest.approx(18_976_000 * 1000 * 4)

    def test_sabesp_posicao_fixa_era_provisoes(self):
        df = pd.concat([
            _quatro_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, "Provisões e Variações Monetárias de Provisões", 80_000),
            _quatro_trimestres("6.01.01.06", "Depreciação e Amortização", 450_000),
        ], ignore_index=True)
        r = _dna_por_texto(df)
        assert r["valor"] == pytest.approx(450_000 * 1000 * 4)

    def test_usiminas_posicao_fixa_era_encargos_cambiais(self):
        df = pd.concat([
            _quatro_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, "Encargos e Variações Monetárias/Cambiais, Líquidas", 20_000),
            _quatro_trimestres("6.01.01.04", "Depreciação e Amortização", 311_166),
        ], ignore_index=True)
        r = _dna_por_texto(df)
        assert r["valor"] == pytest.approx(311_166 * 1000 * 4)

    def test_grendene_posicao_fixa_era_equivalencia_patrimonial(self):
        df = pd.concat([
            _quatro_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, "Resultado de equivalência patrimonial", 1_000),
            _quatro_trimestres("6.01.01.03", "Depreciação e amortização", 24_800),
        ], ignore_index=True)
        r = _dna_por_texto(df)
        assert r["valor"] == pytest.approx(24_800 * 1000 * 4)

    def test_whirlpool_posicao_fixa_era_lucro_operacoes_descontinuadas(self):
        # Whirlpool real também tem uma segunda linha de amortização de
        # direito de uso (arrendamento IFRS16) que a posição fixa nunca
        # capturava — a correção soma as duas.
        df = pd.concat([
            _quatro_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, "Lucro antes dos impostos sobre a renda nas operações descontinuadas", 500_000),
            _quatro_trimestres("6.01.01.03", "Depreciação e amortização", 60_000),
            _quatro_trimestres("6.01.01.16", "Amortização do direito de uso de contratos de arrendamento", 15_000),
        ], ignore_index=True)
        r = _dna_por_texto(df)
        assert r["valor"] == pytest.approx((60_000 + 15_000) * 1000 * 4)
