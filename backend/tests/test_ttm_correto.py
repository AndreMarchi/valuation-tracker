"""
test_ttm_correto.py
Testes de dados/cvm_provider.py::calcular_ttm_correto() — a correção do bug
de TTM documentado no CONTEXT.md: `.tail(4).sum()` direto sobre a série
só-ITR pula o 4º trimestre (que a CVM só reporta via DFP, como total anual)
e cobre ~15 meses em vez de 12.

Os fixtures aqui são deliberadamente REALISTAS nesse aspecto — diferente de
test_fcfe_cvm_inputs.py (que usa um "ITR" sintético com os 4 trimestres já
completos, incluindo um Q4 que na CVM de verdade nunca existe isolado), os
DataFrames de ITR abaixo só têm Q1/Q2/Q3, forçando a derivação via DFP a
entrar em ação de verdade.
"""

import pandas as pd
import pytest
from unittest.mock import patch

from dados.cvm_provider import (
    calcular_ttm_correto,
    buscar_saude_financeira_cvm,
    buscar_inputs_fcfe_cvm,
    CONTA_LUCRO_LIQUIDO,
    CONTA_FCO,
    CONTA_EBIT,
    CONTA_DEPRECIACAO_AMORTIZACAO,
    CONTA_VARIACAO_ATIVOS_PASSIVOS,
    CONTA_RECEITA_LIQUIDA,
)


COLUNAS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC",
    "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]


def _linha_itr(cd_conta, valor, dt_ini, dt_fim, ordem="ÚLTIMO", ds_conta="conta teste"):
    return {
        "CNPJ_CIA": "00.000.000/0001-00", "DT_REFER": dt_fim, "VERSAO": "1",
        "DENOM_CIA": "EMPRESA TESTE S.A.", "CD_CVM": "999999",
        "GRUPO_DFP": "DF Consolidado", "MOEDA": "REAL", "ESCALA_MOEDA": "MIL",
        "ORDEM_EXERC": ordem, "DT_INI_EXERC": dt_ini, "DT_FIM_EXERC": dt_fim,
        "CD_CONTA": cd_conta, "DS_CONTA": ds_conta, "VL_CONTA": str(valor),
        "ST_CONTA_FIXA": "S",
    }


def _linha_dfp_anual(cd_conta, valor, ano, ordem="ÚLTIMO", ds_conta="conta teste"):
    # DFP não reporta trimestre — DT_INI_EXERC cobre o ano inteiro (~365 dias)
    return _linha_itr(cd_conta, valor, f"{ano}-01-01", f"{ano}-12-31", ordem=ordem, ds_conta=ds_conta)


def _df(linhas):
    return pd.DataFrame(linhas, columns=COLUNAS)


def _itr_3_trimestres(cd_conta, ano, q1, q2, q3, ds_conta="conta teste"):
    """ITR realista: só Q1/Q2/Q3 — Q4 nunca existe isolado via ITR."""
    return _df([
        _linha_itr(cd_conta, q1, f"{ano}-01-01", f"{ano}-03-31", ds_conta=ds_conta),
        _linha_itr(cd_conta, q2, f"{ano}-04-01", f"{ano}-06-30", ds_conta=ds_conta),
        _linha_itr(cd_conta, q3, f"{ano}-07-01", f"{ano}-09-30", ds_conta=ds_conta),
    ])


# ─── calcular_ttm_correto() — derivação de Q4 ────────────────────────────────

class TestCalcularTtmCorreto:

    def test_deriva_q4_a_partir_do_anual_dfp(self):
        # Replica o caso real do BEEF3: Q1=185, Q2=458, Q3=120 (mil), anual=848
        # -> Q4 derivado = 848 - (185+458+120) = 85
        itr = _itr_3_trimestres(CONTA_LUCRO_LIQUIDO, 2025, 185, 458, 120)
        dfp = _df([_linha_dfp_anual(CONTA_LUCRO_LIQUIDO, 848, 2025)])

        r = calcular_ttm_correto(itr, dfp, CONTA_LUCRO_LIQUIDO)

        assert r["quantidade_trimestres_reais"] == 4
        assert r["trimestres_usados"] == ["2025T1", "2025T2", "2025T3", "2025T4"]
        # soma do ano fiscal completo deve bater exatamente com o anual do DFP
        assert r["valor"] == pytest.approx(848 * 1000)  # x1000 pela ESCALA_MOEDA

    def test_nao_deriva_q4_quando_falta_um_trimestre_itr(self):
        # Falta Q2 -> não deriva Q4 pra esse ano, mesmo com o DFP anual disponível
        itr = _df([
            _linha_itr(CONTA_LUCRO_LIQUIDO, 185, "2025-01-01", "2025-03-31"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 120, "2025-07-01", "2025-09-30"),
        ])
        dfp = _df([_linha_dfp_anual(CONTA_LUCRO_LIQUIDO, 848, 2025)])

        r = calcular_ttm_correto(itr, dfp, CONTA_LUCRO_LIQUIDO)

        assert "2025T4" not in r["trimestres_usados"]
        assert r["quantidade_trimestres_reais"] == 2
        assert r["valor"] is None  # não tem 4 trimestres reais -> não estima

    def test_cruza_virada_de_ano_fiscal(self):
        # 2025 completo (com Q4 derivado) + começo de 2026 -> os "4 mais
        # recentes" devem pular o 1T25 e pegar 4T25(derivado)+1T26+2T26+3T26
        itr = _df([
            _linha_itr(CONTA_LUCRO_LIQUIDO, 100, "2025-01-01", "2025-03-31"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 100, "2025-04-01", "2025-06-30"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 100, "2025-07-01", "2025-09-30"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 50, "2026-01-01", "2026-03-31"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 60, "2026-04-01", "2026-06-30"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 70, "2026-07-01", "2026-09-30"),
        ])
        dfp = _df([_linha_dfp_anual(CONTA_LUCRO_LIQUIDO, 400, 2025)])  # Q4-2025 derivado = 100

        r = calcular_ttm_correto(itr, dfp, CONTA_LUCRO_LIQUIDO)

        assert r["trimestres_usados"] == ["2025T4", "2026T1", "2026T2", "2026T3"]
        assert r["quantidade_trimestres_reais"] == 4
        assert r["valor"] == pytest.approx((100 + 50 + 60 + 70) * 1000)

    def test_nao_sobrescreve_q4_ja_reportado_isolado(self):
        # Caso raro: se o Q4 já existir isolado no ITR (não deveria acontecer
        # na prática, mas não custa proteger), não deriva por cima dele.
        itr = _df([
            _linha_itr(CONTA_LUCRO_LIQUIDO, 100, "2025-01-01", "2025-03-31"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 100, "2025-04-01", "2025-06-30"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 100, "2025-07-01", "2025-09-30"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 999, "2025-10-01", "2025-12-31"),  # Q4 "de verdade"
        ])
        dfp = _df([_linha_dfp_anual(CONTA_LUCRO_LIQUIDO, 400, 2025)])  # implicaria Q4=100, não 999

        r = calcular_ttm_correto(itr, dfp, CONTA_LUCRO_LIQUIDO)

        assert r["valor"] == pytest.approx((100 + 100 + 100 + 999) * 1000)  # usou o 999 real, não derivou

    def test_reaproveita_dedup_de_trimestre_vs_acumulado(self):
        # Mesma armadilha documentada pra _extrair_serie: ITR reporta
        # trimestre isolado E acumulado no exercício pro mesmo DT_FIM_EXERC.
        # calcular_ttm_correto não pode herdar esse bug.
        itr = _df([
            _linha_itr(CONTA_LUCRO_LIQUIDO, 185, "2025-01-01", "2025-03-31"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 458, "2025-04-01", "2025-06-30"),
            _linha_itr(CONTA_LUCRO_LIQUIDO, 643, "2025-01-01", "2025-06-30"),  # acumulado duplicado (deve ser ignorado)
            _linha_itr(CONTA_LUCRO_LIQUIDO, 120, "2025-07-01", "2025-09-30"),
        ])
        dfp = _df([_linha_dfp_anual(CONTA_LUCRO_LIQUIDO, 848, 2025)])

        r = calcular_ttm_correto(itr, dfp, CONTA_LUCRO_LIQUIDO)

        assert r["valor"] == pytest.approx(848 * 1000)  # não deve ter somado o acumulado duplicado

    def test_series_vazias_retorna_none_graciosamente(self):
        vazio = _df([])
        r = calcular_ttm_correto(vazio, vazio, CONTA_LUCRO_LIQUIDO)
        assert r == {"valor": None, "trimestres_usados": [], "quantidade_trimestres_reais": 0}

    def test_dfp_sem_ano_correspondente_nao_quebra(self):
        # DFP existe mas não cobre o ano do ITR disponível (ex: empresa nova)
        itr = _itr_3_trimestres(CONTA_LUCRO_LIQUIDO, 2025, 100, 100, 100)
        dfp = _df([_linha_dfp_anual(CONTA_LUCRO_LIQUIDO, 999, 2020)])  # ano irrelevante

        r = calcular_ttm_correto(itr, dfp, CONTA_LUCRO_LIQUIDO)

        assert "2025T4" not in r["trimestres_usados"]
        assert r["valor"] is None  # só 3 trimestres reais disponíveis


# ─── convenção ACUMULADA do DFC (bug achado durante a investigação do D&A) ──

class TestConvencaoAcumuladaDoDfc:
    """
    O DFC (Demonstração de Fluxo de Caixa) no ITR NUNCA reporta trimestre
    isolado — só ACUMULADO desde 1º/jan do ano fiscal (DT_INI_EXERC é
    sempre 1º/jan, mesmo pro "3º trimestre", que na prática já é 9 meses
    acumulados). Confirmado sistematicamente: 441 de 451 empresas têm essa
    característica na conta FCO (6.01). Diferente da DRE (testada acima),
    que reporta os dois: trimestre isolado E acumulado, com DT_INI_EXERC
    apontando pro início do próprio trimestre a partir do Q2.

    Os fixtures abaixo usam DT_INI_EXERC = 1º/jan (não o início do próprio
    trimestre) pra Q2/Q3 — replicando a convenção real do DFC — e verificam
    que calcular_ttm_correto() isola corretamente por diferença em vez de
    somar valores acumulados como se fossem isolados (o que inflava/
    deflacionava o TTM — ver CONTEXT.md e a comparação real: Banco Santander
    caiu de R$119,4bi pra R$64,4bi de FCO TTM só com essa correção).
    """

    def _linha_acumulada(self, cd_conta, valor, ano, mes_fim, dia_fim):
        # DT_INI_EXERC sempre 1º/jan -> convenção acumulada do DFC
        return _linha_itr(cd_conta, valor, f"{ano}-01-01", f"{ano}-{mes_fim:02d}-{dia_fim:02d}")

    def test_isola_trimestres_acumulados_do_dfc(self):
        # Réplica do caso real da Petrobras: Q1=18976 (=isolado, sempre),
        # Q2 acumulado=39928 (isolado real = 39928-18976=20952),
        # Q3 acumulado=62317 (isolado real = 62317-39928=22389)
        itr = _df([
            self._linha_acumulada(CONTA_FCO, 18976, 2025, 3, 31),
            self._linha_acumulada(CONTA_FCO, 39928, 2025, 6, 30),
            self._linha_acumulada(CONTA_FCO, 62317, 2025, 9, 30),
        ])
        dfp = _df([_linha_dfp_anual(CONTA_FCO, 84388, 2025)])  # acumulado do ano inteiro

        r = calcular_ttm_correto(itr, dfp, CONTA_FCO)

        # Q4 isolado = anual - acumulado-ate-Q3 = 84388 - 62317 = 22071
        # soma do ano fiscal completo = 18976+20952+22389+22071 = 84388 (bate com o anual, por construção)
        assert r["quantidade_trimestres_reais"] == 4
        assert r["valor"] == pytest.approx(84388 * 1000)

    def test_trimestre_acumulado_sem_trimestre_anterior_nao_e_isolado(self):
        # Q1 falta -> não dá pra isolar Q2 acumulado (não sabe quanto
        # subtrair) -> não inclui esse ponto, não finge que é isolado
        itr = _df([
            self._linha_acumulada(CONTA_FCO, 39928, 2025, 6, 30),  # Q2 acumulado, sem Q1
            self._linha_acumulada(CONTA_FCO, 62317, 2025, 9, 30),  # Q3 acumulado
        ])
        dfp = _df([_linha_dfp_anual(CONTA_FCO, 84388, 2025)])

        r = calcular_ttm_correto(itr, dfp, CONTA_FCO)

        assert r["valor"] is None  # nenhum trimestre desse ano pôde ser isolado com confiança

    def test_convencao_isolada_e_acumulada_dao_mesmo_resultado_quando_dado_e_consistente(self):
        # Prova de equivalência: o mesmo ano fiscal, representado com a
        # convenção ISOLADA (DRE) ou ACUMULADA (DFC), deve produzir o MESMO
        # TTM final — a função generaliza os dois casos corretamente.
        itr_isolado = _itr_3_trimestres(CONTA_FCO, 2025, 18976, 20952, 22389)
        itr_acumulado = _df([
            self._linha_acumulada(CONTA_FCO, 18976, 2025, 3, 31),
            self._linha_acumulada(CONTA_FCO, 39928, 2025, 6, 30),   # 18976+20952
            self._linha_acumulada(CONTA_FCO, 62317, 2025, 9, 30),   # +22389
        ])
        dfp = _df([_linha_dfp_anual(CONTA_FCO, 84388, 2025)])

        r_isolado = calcular_ttm_correto(itr_isolado, dfp, CONTA_FCO)
        r_acumulado = calcular_ttm_correto(itr_acumulado, dfp, CONTA_FCO)

        assert r_isolado["valor"] == pytest.approx(r_acumulado["valor"])
        assert r_isolado["valor"] == pytest.approx(84388 * 1000)


# ─── integração: buscar_saude_financeira_cvm() usa o TTM corrigido ─────────

class TestIntegracaoSaudeFinanceiraComTtmCorreto:

    def _mock_carregar_demo(self, dre_itr, dfc_itr, dre_dfp, dfc_dfp, bpp=None):
        vazio = _df([])
        def _side_effect(tipo, cd_cvm):
            return {
                "itr_dre": dre_itr, "itr_dfc": dfc_itr,
                "dfp_dre": dre_dfp, "dfp_dfc": dfc_dfp,
                "itr_bpp": bpp if bpp is not None else vazio,
                "dfp_bpp": vazio,
            }.get(tipo, vazio)
        return _side_effect

    def test_qualidade_lucro_usa_q4_derivado(self):
        # FCO e lucro com o mesmo gap de Q4 que o BEEF3 real tem
        dre_itr = _itr_3_trimestres(CONTA_LUCRO_LIQUIDO, 2025, 185, 458, 120)
        dre_itr = pd.concat([dre_itr, _itr_3_trimestres(CONTA_RECEITA_LIQUIDA, 2025, 1000, 1000, 1000)], ignore_index=True)
        dre_dfp = _df([
            _linha_dfp_anual(CONTA_LUCRO_LIQUIDO, 848, 2025),
            _linha_dfp_anual(CONTA_RECEITA_LIQUIDA, 4000, 2025),
        ])
        dfc_itr = _itr_3_trimestres(CONTA_FCO, 2025, 200, 500, 150)
        dfc_dfp = _df([_linha_dfp_anual(CONTA_FCO, 1000, 2025)])  # Q4 FCO derivado = 150

        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre_itr, dfc_itr, dre_dfp, dfc_dfp)):
            r = buscar_saude_financeira_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        # lucro TTM = 848*1000 (ano fiscal completo, com Q4 derivado)
        # fco TTM = 1000*1000 (idem)
        assert r["qualidade_lucro"] == pytest.approx(round((1000 * 1000) / (848 * 1000), 2))


# ─── integração: buscar_inputs_fcfe_cvm() usa o TTM corrigido ─────────────

class TestIntegracaoFcfeComTtmCorreto:

    def _mock_carregar_demo(self, dre_itr, dfc_itr, dre_dfp, dfc_dfp):
        vazio = _df([])
        def _side_effect(tipo, cd_cvm):
            return {
                "itr_dre": dre_itr, "itr_dfc": dfc_itr,
                "dfp_dre": dre_dfp, "dfp_dfc": dfc_dfp,
            }.get(tipo, vazio)
        return _side_effect

    def test_lucro_liquido_fcfe_usa_q4_derivado(self):
        # D&A agora é extraído por TEXTO (não pela posição fixa
        # CONTA_DEPRECIACAO_AMORTIZACAO — ver DEPRECIACAO_PREFIXO em
        # cvm_provider.py e CONTEXT.md), por isso o fixture usa um DS_CONTA
        # realista ("Depreciação e amortização") em vez do genérico "conta
        # teste" — sem isso, calcular_ttm_por_texto não bate a linha.
        dre_itr = _itr_3_trimestres(CONTA_LUCRO_LIQUIDO, 2025, 185, 458, 120)
        dre_dfp = _df([_linha_dfp_anual(CONTA_LUCRO_LIQUIDO, 848, 2025)])
        dfc_itr = pd.concat([
            _itr_3_trimestres(CONTA_DEPRECIACAO_AMORTIZACAO, 2025, 10, 10, 10, ds_conta="Depreciação e amortização"),
            _itr_3_trimestres(CONTA_VARIACAO_ATIVOS_PASSIVOS, 2025, -5, -5, -5),
        ], ignore_index=True)
        dfc_dfp = _df([
            _linha_dfp_anual(CONTA_DEPRECIACAO_AMORTIZACAO, 40, 2025, ds_conta="Depreciação e amortização"),
            _linha_dfp_anual(CONTA_VARIACAO_ATIVOS_PASSIVOS, -20, 2025),
        ])

        with patch("dados.cvm_provider.buscar_cd_cvm", return_value=999999), \
             patch("dados.cvm_provider._carregar_demo", side_effect=self._mock_carregar_demo(dre_itr, dfc_itr, dre_dfp, dfc_dfp)):
            r = buscar_inputs_fcfe_cvm("TEST3", "EMPRESA TESTE S.A.")

        assert r["disponivel"] is True
        assert r["lucro_liquido"] == pytest.approx(848 * 1000)
        assert r["depreciacao"] == pytest.approx(40 * 1000)
        # variacao TTM (convenção CVM) = -20*1000 -> delta_ccl (academica, invertido) = +20*1000
        assert r["delta_ccl"] == pytest.approx(20 * 1000)
