"""
test_fcfe_valuation.py
Testes de valuation/fcfe_valuation.py — a orquestração ponta a ponta do FCFE:
buscar_inputs_fcfe_cvm() -> calcular_fcfe() -> valuation_fcfe_dois_estagios(),
sector-aware (bancos/seguradoras retornam indisponibilidade explícita).

Segue a mesma convenção de mock do resto da suíte (test_fcfe_cvm_inputs.py,
test_ttm_correto.py): buscar_inputs_fcfe_cvm() é mockado com valores REAIS
(magnitudes verificadas contra a BEEF3/Minerva durante a investigação desta
sessão — ver CONTEXT.md), não recalculado a partir de CSV bruto — o objetivo
aqui é testar a ORQUESTRAÇÃO (fcfe_valuation.py), não re-testar a extração
CVM em si (já coberta por test_fcfe_cvm_inputs.py/test_extrair_por_texto.py).
"""

import pytest
from unittest.mock import patch

from valuation.fcfe_valuation import calcular_valuation_fcfe, eh_setor_bancario_ou_segurador


# Valores reais do TTM da BEEF3/Minerva, obtidos via buscar_inputs_fcfe_cvm()
# durante a investigação desta sessão (ver CONTEXT.md) — inclui o caso real
# de FCFE negativo por desalavancagem pontual (amortização >> novas dívidas).
_INPUTS_BEEF3_REAIS = {
    "disponivel": True,
    "cd_cvm": 20931,
    "lucro_liquido": 750551000.0,
    "depreciacao": 992594000.0,
    "delta_ccl": -82103000.0,
    "capex": 1192098000.0,
    "novas_dividas_emitidas": 5938402000.0,
    "amortizacao_dividas": 11540547000.0,
    "fcfe_completo_disponivel": True,
}


class TestFluxoCompletoTickerNaoFinanceiro:

    def test_beef3_fluxo_completo_com_dado_real(self):
        with patch("valuation.fcfe_valuation.buscar_inputs_fcfe_cvm", return_value=_INPUTS_BEEF3_REAIS):
            r = calcular_valuation_fcfe(
                ticker="BEEF3",
                nome_empresa="MINERVA S.A.",
                setor="Alimentos Processados",
                ke=0.1968,
                taxa_crescimento_explicito=0.177,
                g_perpetuo=0.04,
                anos_explicitos=5,
                num_acoes=1_000_540_000.0,
            )

        assert r["disponivel"] is True
        assert r["cd_cvm"] == 20931

        base = r["fcfe_ano_base"]
        assert base["lucro_liquido"] == pytest.approx(750551000.0)
        # FCFE = lucro - reinvestimento_liquido + delta_divida_liquida
        assert base["reinvestimento_liquido"] == pytest.approx((1192098000.0 - 992594000.0) + (-82103000.0))
        assert base["delta_divida_liquida"] == pytest.approx(5938402000.0 - 11540547000.0)
        assert base["fcfe"] == pytest.approx(
            750551000.0 - base["reinvestimento_liquido"] + base["delta_divida_liquida"]
        )

        # projeção existe (número de ações válido) — mesmo com FCFE ano-base
        # negativo, o pipeline não quebra, só propaga um valor justo negativo
        assert r["projecao"] is not None
        assert r["projecao"]["fcfe_projetados"][0] == pytest.approx(base["fcfe"] * 1.177)
        assert r["projecao"]["valor_justo_por_acao"] is not None
        assert r["projecao"]["valor_justo_por_acao"] < 0  # caso real: desalavancagem pontual no TTM

        assert r["premissas"] == {
            "ke": 0.1968,
            "taxa_crescimento_explicito": 0.177,
            "g_perpetuo": 0.04,
            "anos_explicitos": 5,
        }

    def test_num_acoes_invalido_retorna_ano_base_sem_projecao(self):
        with patch("valuation.fcfe_valuation.buscar_inputs_fcfe_cvm", return_value=_INPUTS_BEEF3_REAIS):
            r = calcular_valuation_fcfe(
                ticker="BEEF3", nome_empresa="MINERVA S.A.", setor="Alimentos Processados",
                ke=0.15, taxa_crescimento_explicito=0.10, g_perpetuo=0.04, anos_explicitos=5,
                num_acoes=0,
            )

        assert r["disponivel"] is True
        assert r["fcfe_ano_base"] is not None  # ano base calcula independente de num_acoes
        assert r["projecao"] is None
        assert "Número de ações inválido" in r["erro"]


class TestSetorBancarioOuSegurador:

    @pytest.mark.parametrize("setor", [
        "Intermediários Financeiros", "Bancos", "Seguradoras",
        "intermediários financeiros", "BANCOS",
    ])
    def test_detecta_setores_financeiros(self, setor):
        assert eh_setor_bancario_ou_segurador(setor) is True

    @pytest.mark.parametrize("setor", [
        "Alimentos Processados", "Energia Elétrica", "Varejo", "Tecnologia", "",
    ])
    def test_nao_detecta_setores_nao_financeiros(self, setor):
        assert eh_setor_bancario_ou_segurador(setor) is False

    def test_banco_retorna_indisponibilidade_explicita_sem_consultar_cvm(self):
        with patch("valuation.fcfe_valuation.buscar_inputs_fcfe_cvm") as mock_buscar:
            r = calcular_valuation_fcfe(
                ticker="ITUB4", nome_empresa="ITAU UNIBANCO HOLDING S.A.",
                setor="Intermediários Financeiros",
                ke=0.19, taxa_crescimento_explicito=0.10, g_perpetuo=0.04, anos_explicitos=5,
                num_acoes=11_026_900_000.0,
            )

        assert r == {"disponivel": False, "erro": "FCFE indisponível — taxonomia COSIF/SUSEP não suportada"}
        mock_buscar.assert_not_called()  # nem consulta a CVM — mensagem específica, sem custo extra

    def test_seguradora_retorna_indisponibilidade_explicita(self):
        with patch("valuation.fcfe_valuation.buscar_inputs_fcfe_cvm") as mock_buscar:
            r = calcular_valuation_fcfe(
                ticker="BBSE3", nome_empresa="BB SEGURIDADE PARTICIPACOES S.A.",
                setor="Seguradoras",
                ke=0.16, taxa_crescimento_explicito=0.08, g_perpetuo=0.04, anos_explicitos=5,
                num_acoes=1_000_000_000.0,
            )

        assert r["disponivel"] is False
        assert "COSIF/SUSEP" in r["erro"]
        mock_buscar.assert_not_called()


class TestFcfeCompletoDisponivelFalsoPropagaSemQuebrar:

    def test_campo_faltando_retorna_indisponivel_com_inputs_parciais(self):
        inputs_incompletos = {
            "disponivel": True,
            "cd_cvm": 12345,
            "lucro_liquido": 500_000_000.0,
            "depreciacao": 80_000_000.0,
            "delta_ccl": -10_000_000.0,
            "capex": None,  # não bateu nenhuma linha de texto pra esse ticker
            "novas_dividas_emitidas": None,
            "amortizacao_dividas": None,
            "fcfe_completo_disponivel": False,
        }
        with patch("valuation.fcfe_valuation.buscar_inputs_fcfe_cvm", return_value=inputs_incompletos):
            r = calcular_valuation_fcfe(
                ticker="XYZW3", nome_empresa="EMPRESA TESTE S.A.", setor="Varejo",
                ke=0.15, taxa_crescimento_explicito=0.08, g_perpetuo=0.04, anos_explicitos=5,
                num_acoes=100_000_000.0,
            )

        assert r["disponivel"] is False
        assert "incompletos" in r["erro"]
        assert r["cd_cvm"] == 12345
        assert r["inputs_parciais"]["lucro_liquido"] == pytest.approx(500_000_000.0)
        assert r["inputs_parciais"]["capex"] is None
        assert r["inputs_parciais"]["novas_dividas_emitidas"] is None
        assert r["inputs_parciais"]["amortizacao_dividas"] is None
        # não deve tentar calcular_fcfe() com campo None -> nem "fcfe_ano_base" nem "projecao" no retorno
        assert "fcfe_ano_base" not in r
        assert "projecao" not in r

    def test_cvm_totalmente_indisponivel_propaga_erro_original(self):
        with patch(
            "valuation.fcfe_valuation.buscar_inputs_fcfe_cvm",
            return_value={"disponivel": False, "erro": "Empresa não encontrada na CVM: XYZW3"},
        ):
            r = calcular_valuation_fcfe(
                ticker="XYZW3", nome_empresa="", setor="Varejo",
                ke=0.15, taxa_crescimento_explicito=0.08, g_perpetuo=0.04, anos_explicitos=5,
                num_acoes=100_000_000.0,
            )

        assert r == {"disponivel": False, "erro": "Empresa não encontrada na CVM: XYZW3"}
