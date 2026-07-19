import pytest
from valuation.fcfe import (
    calcular_fcfe,
    projetar_fcfe,
    valor_terminal_fcfe,
    valuation_fcfe_dois_estagios,
)


class TestCalcularFCFE:
    def test_caso_basico(self):
        r = calcular_fcfe(
            lucro_liquido=1000,
            capex=400,
            depreciacao=150,
            delta_ccl=50,
            novas_dividas_emitidas=200,
            amortizacao_dividas=100,
        )
        # reinvestimento = (400-150)+50 = 300
        # delta_divida = 200-100 = 100
        # fcfe = 1000 - 300 + 100 = 800
        assert r.reinvestimento_liquido == 300
        assert r.delta_divida_liquida == 100
        assert r.fcfe == 800
        assert r.alerta is None

    def test_lucro_liquido_negativo_gera_alerta(self):
        r = calcular_fcfe(
            lucro_liquido=-500,
            capex=200,
            depreciacao=100,
            delta_ccl=0,
            novas_dividas_emitidas=0,
            amortizacao_dividas=0,
        )
        assert r.alerta is not None
        assert "negativo" in r.alerta.lower()

    def test_reinvestimento_negativo_eh_permitido(self):
        # Depreciação > CAPEX é comum em empresas capital-light / maduras
        r = calcular_fcfe(
            lucro_liquido=1000,
            capex=50,
            depreciacao=150,
            delta_ccl=0,
            novas_dividas_emitidas=0,
            amortizacao_dividas=0,
        )
        assert r.reinvestimento_liquido == -100
        assert r.fcfe == 1100

    def test_amortizacao_maior_que_emissao_reduz_fcfe(self):
        r = calcular_fcfe(
            lucro_liquido=1000,
            capex=0,
            depreciacao=0,
            delta_ccl=0,
            novas_dividas_emitidas=50,
            amortizacao_dividas=300,
        )
        assert r.delta_divida_liquida == -250
        assert r.fcfe == 750


class TestProjetarFCFE:
    def test_projecao_crescimento_constante(self):
        proj = projetar_fcfe(100, 0.10, 3)
        assert proj == pytest.approx([110, 121, 133.1])

    def test_anos_invalido_levanta_erro(self):
        with pytest.raises(ValueError):
            projetar_fcfe(100, 0.10, 0)

    def test_crescimento_negativo(self):
        proj = projetar_fcfe(100, -0.05, 2)
        assert proj == pytest.approx([95, 90.25])


class TestValorTerminalFCFE:
    def test_calculo_normal(self):
        vt = valor_terminal_fcfe(fcfe_ultimo_ano_explicito=100, ke=0.12, g_perpetuo=0.03)
        # 100 * 1.03 / (0.12-0.03) = 103/0.09
        assert vt.valor == pytest.approx(103 / 0.09)
        assert vt.alerta is None

    def test_ke_igual_g_retorna_none_com_alerta(self):
        vt = valor_terminal_fcfe(100, ke=0.08, g_perpetuo=0.08)
        assert vt.valor is None
        assert "indefinido" in vt.alerta.lower()

    def test_ke_menor_que_g_retorna_none_com_alerta(self):
        vt = valor_terminal_fcfe(100, ke=0.05, g_perpetuo=0.08)
        assert vt.valor is None
        assert vt.alerta is not None


class TestValuationFCFEDoisEstagios:
    def test_caso_completo(self):
        res = valuation_fcfe_dois_estagios(
            fcfe_ano_base=100,
            taxa_crescimento_explicito=0.10,
            anos_explicitos=5,
            ke=0.13,
            g_perpetuo=0.04,
            numero_acoes=1000,
        )
        assert res.alerta is None
        assert res.valor_justo_equity is not None
        assert res.valor_justo_por_acao == pytest.approx(
            res.valor_justo_equity / 1000
        )
        # sanity: valor presente explícito deve ser positivo e menor que a soma nominal
        soma_nominal = sum(res.fcfe_projetados)
        assert 0 < res.valor_presente_fcfe_explicito < soma_nominal

    def test_numero_acoes_invalido(self):
        res = valuation_fcfe_dois_estagios(
            fcfe_ano_base=100,
            taxa_crescimento_explicito=0.10,
            anos_explicitos=5,
            ke=0.13,
            g_perpetuo=0.04,
            numero_acoes=0,
        )
        assert res.valor_justo_por_acao is None
        assert "ações inválido" in res.alerta

    def test_ke_menor_que_g_propaga_alerta(self):
        res = valuation_fcfe_dois_estagios(
            fcfe_ano_base=100,
            taxa_crescimento_explicito=0.05,
            anos_explicitos=5,
            ke=0.06,
            g_perpetuo=0.07,
            numero_acoes=1000,
        )
        assert res.valor_justo_por_acao is None
        assert res.alerta is not None

    def test_fair_value_diminui_com_ke_maior(self):
        base = dict(
            fcfe_ano_base=100,
            taxa_crescimento_explicito=0.08,
            anos_explicitos=5,
            g_perpetuo=0.03,
            numero_acoes=1000,
        )
        res_ke_baixo = valuation_fcfe_dois_estagios(ke=0.10, **base)
        res_ke_alto = valuation_fcfe_dois_estagios(ke=0.16, **base)
        assert res_ke_alto.valor_justo_por_acao < res_ke_baixo.valor_justo_por_acao