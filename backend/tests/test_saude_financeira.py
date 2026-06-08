"""
test_saude_financeira.py
Testes unitários para backend/valuation/saude_financeira.py
"""

import pytest
from valuation.saude_financeira import calcular_saude_financeira, extrair_crescimento_cvm


# ─── fixtures ────────────────────────────────────────────────────────────────

def _dados_completos(**kwargs):
    """Retorna um dict de dados CVM completo com valores padrão saudáveis."""
    base = {
        "disponivel": True,
        "cd_cvm": 9512,
        "tendencia_receita": "crescendo",
        "qualidade_lucro": 1.3,
        "margens_pct": [14.0, 15.0, 16.0, 15.5, 16.5, 17.0],
        "receita_trimestral": [
            {"periodo": "2023T1", "valor": 10000},
            {"periodo": "2023T2", "valor": 11000},
            {"periodo": "2023T3", "valor": 11500},
            {"periodo": "2023T4", "valor": 12000},
            {"periodo": "2024T1", "valor": 12500},
            {"periodo": "2024T2", "valor": 13000},
        ],
        "lucro_trimestral": [
            {"periodo": "2023T1", "valor": 1400},
            {"periodo": "2023T2", "valor": 1650},
            {"periodo": "2023T3", "valor": 1840},
            {"periodo": "2023T4", "valor": 1860},
            {"periodo": "2024T1", "valor": 2063},
            {"periodo": "2024T2", "valor": 2210},
        ],
        "fco_trimestral": [
            {"periodo": "2023T1", "valor": 1600},
            {"periodo": "2023T2", "valor": 1800},
        ],
    }
    base.update(kwargs)
    return base


# ─── calcular_saude_financeira ───────────────────────────────────────────────

class TestCalcularSaudeFinanceira:

    def test_retorna_indisponivel_quando_dados_ausentes(self):
        resultado = calcular_saude_financeira({"disponivel": False, "erro": "não encontrado"})
        assert resultado["disponivel"] is False
        assert "erro" in resultado

    def test_retorna_indisponivel_sem_chave(self):
        resultado = calcular_saude_financeira({})
        assert resultado["disponivel"] is False

    def test_empresa_saudavel_score_alto(self):
        dados = _dados_completos(
            tendencia_receita="crescendo",
            qualidade_lucro=1.5,
            margens_pct=[18.0, 19.0, 20.0, 19.5, 20.5, 21.0],
        )
        resultado = calcular_saude_financeira(dados)
        assert resultado["disponivel"] is True
        assert resultado["score"] >= 7.0
        assert resultado["classificacao"] in ("Boa", "Excelente")

    def test_empresa_problematica_score_baixo(self):
        dados = _dados_completos(
            tendencia_receita="caindo",
            qualidade_lucro=0.3,
            margens_pct=[-5.0, -3.0, -2.0, -4.0],
        )
        resultado = calcular_saude_financeira(dados)
        assert resultado["disponivel"] is True
        assert resultado["score"] <= 3.0
        assert resultado["classificacao"] in ("Fraca", "Crítica")

    def test_tendencia_crescendo_aumenta_score(self):
        base = _dados_completos(tendencia_receita="estável", qualidade_lucro=1.0, margens_pct=[10.0] * 4)
        crescendo = _dados_completos(tendencia_receita="crescendo", qualidade_lucro=1.0, margens_pct=[10.0] * 4)
        assert calcular_saude_financeira(crescendo)["score"] > calcular_saude_financeira(base)["score"]

    def test_tendencia_caindo_diminui_score(self):
        base = _dados_completos(tendencia_receita="estável", qualidade_lucro=1.0, margens_pct=[10.0] * 4)
        caindo = _dados_completos(tendencia_receita="caindo", qualidade_lucro=1.0, margens_pct=[10.0] * 4)
        assert calcular_saude_financeira(caindo)["score"] < calcular_saude_financeira(base)["score"]

    def test_qualidade_lucro_alta_gera_destaque(self):
        dados = _dados_completos(qualidade_lucro=1.5)
        resultado = calcular_saude_financeira(dados)
        assert any("caixa" in d.lower() or "fco" in d.lower() for d in resultado.get("destaques", []))

    def test_qualidade_lucro_baixa_gera_alerta(self):
        dados = _dados_completos(qualidade_lucro=0.3)
        resultado = calcular_saude_financeira(dados)
        assert len(resultado.get("alertas", [])) > 0

    def test_qualidade_lucro_none_nao_quebra(self):
        dados = _dados_completos(qualidade_lucro=None)
        resultado = calcular_saude_financeira(dados)
        assert resultado["disponivel"] is True
        assert "score" in resultado

    def test_score_clampado_entre_0_e_10(self):
        # situação extremamente boa
        dados = _dados_completos(
            tendencia_receita="crescendo",
            qualidade_lucro=5.0,
            margens_pct=[50.0] * 6,
        )
        resultado = calcular_saude_financeira(dados)
        assert 0.0 <= resultado["score"] <= 10.0

        # situação extremamente ruim
        dados2 = _dados_completos(
            tendencia_receita="caindo",
            qualidade_lucro=0.0,
            margens_pct=[-50.0] * 6,
        )
        resultado2 = calcular_saude_financeira(dados2)
        assert 0.0 <= resultado2["score"] <= 10.0

    def test_classificacao_excelente(self):
        dados = _dados_completos(tendencia_receita="crescendo", qualidade_lucro=2.0, margens_pct=[25.0] * 6)
        resultado = calcular_saude_financeira(dados)
        assert resultado["classificacao"] in ("Excelente", "Boa")

    def test_classificacao_critica(self):
        dados = _dados_completos(tendencia_receita="caindo", qualidade_lucro=0.1, margens_pct=[-10.0] * 6)
        resultado = calcular_saude_financeira(dados)
        assert resultado["classificacao"] in ("Crítica", "Fraca")

    def test_campos_obrigatorios_no_retorno(self):
        dados = _dados_completos()
        resultado = calcular_saude_financeira(dados)
        for campo in ["disponivel", "score", "classificacao", "tendencia_receita",
                      "alertas", "destaques", "receita_trimestral", "lucro_trimestral"]:
            assert campo in resultado, f"Campo ausente: {campo}"

    def test_margens_vazias_nao_quebra(self):
        dados = _dados_completos(margens_pct=[])
        resultado = calcular_saude_financeira(dados)
        assert resultado["disponivel"] is True

    def test_cd_cvm_preservado_no_retorno(self):
        dados = _dados_completos(cd_cvm=9512)
        resultado = calcular_saude_financeira(dados)
        assert resultado.get("cd_cvm") == 9512

    def test_margem_em_expansao_gera_destaque(self):
        # margem subindo claramente nos últimos períodos
        dados = _dados_completos(margens_pct=[10.0, 10.5, 11.0, 11.5, 12.0, 13.5])
        resultado = calcular_saude_financeira(dados)
        assert resultado["disponivel"] is True


# ─── extrair_crescimento_cvm ─────────────────────────────────────────────────

class TestExtrairCrescimentoCvm:

    def test_retorna_none_quando_indisponivel(self):
        assert extrair_crescimento_cvm({"disponivel": False}) is None

    def test_retorna_none_quando_poucos_trimestres(self):
        dados = _dados_completos(receita_trimestral=[{"periodo": "2024T1", "valor": 1000}])
        assert extrair_crescimento_cvm(dados) is None

    def test_crescimento_positivo(self):
        dados = _dados_completos(receita_trimestral=[
            {"periodo": "2022T1", "valor": 1000},
            {"periodo": "2022T2", "valor": 1000},
            {"periodo": "2022T3", "valor": 1000},
            {"periodo": "2022T4", "valor": 1000},
            {"periodo": "2023T1", "valor": 1200},
            {"periodo": "2023T2", "valor": 1200},
            {"periodo": "2023T3", "valor": 1200},
            {"periodo": "2023T4", "valor": 1200},
        ])
        crescimento = extrair_crescimento_cvm(dados)
        assert crescimento is not None
        assert abs(crescimento - 0.20) < 0.01  # 20% de crescimento

    def test_crescimento_negativo(self):
        dados = _dados_completos(receita_trimestral=[
            {"periodo": "2022T1", "valor": 1000},
            {"periodo": "2022T2", "valor": 1000},
            {"periodo": "2022T3", "valor": 1000},
            {"periodo": "2022T4", "valor": 1000},
            {"periodo": "2023T1", "valor": 800},
            {"periodo": "2023T2", "valor": 800},
            {"periodo": "2023T3", "valor": 800},
            {"periodo": "2023T4", "valor": 800},
        ])
        crescimento = extrair_crescimento_cvm(dados)
        assert crescimento is not None
        assert crescimento < 0

    def test_crescimento_limitado_em_50_pct(self):
        # crescimento absurdo deve ser clampado em 50%
        dados = _dados_completos(receita_trimestral=[
            {"periodo": "2022T1", "valor": 100},
            {"periodo": "2022T2", "valor": 100},
            {"periodo": "2022T3", "valor": 100},
            {"periodo": "2022T4", "valor": 100},
            {"periodo": "2023T1", "valor": 10000},
            {"periodo": "2023T2", "valor": 10000},
            {"periodo": "2023T3", "valor": 10000},
            {"periodo": "2023T4", "valor": 10000},
        ])
        crescimento = extrair_crescimento_cvm(dados)
        assert crescimento is not None
        assert crescimento <= 0.50

    def test_crescimento_limitado_em_menos_30_pct(self):
        dados = _dados_completos(receita_trimestral=[
            {"periodo": "2022T1", "valor": 10000},
            {"periodo": "2022T2", "valor": 10000},
            {"periodo": "2022T3", "valor": 10000},
            {"periodo": "2022T4", "valor": 10000},
            {"periodo": "2023T1", "valor": 100},
            {"periodo": "2023T2", "valor": 100},
            {"periodo": "2023T3", "valor": 100},
            {"periodo": "2023T4", "valor": 100},
        ])
        crescimento = extrair_crescimento_cvm(dados)
        assert crescimento is not None
        assert crescimento >= -0.30

    def test_retorna_none_com_menos_de_4_trimestres(self):
        dados = _dados_completos(receita_trimestral=[
            {"periodo": "2023T1", "valor": 1000},
            {"periodo": "2023T2", "valor": 1100},
            {"periodo": "2023T3", "valor": 1050},
        ])
        assert extrair_crescimento_cvm(dados) is None

    def test_crescimento_estavel_proximo_de_zero(self):
        dados = _dados_completos(receita_trimestral=[
            {"periodo": "2022T1", "valor": 1000},
            {"periodo": "2022T2", "valor": 1000},
            {"periodo": "2022T3", "valor": 1000},
            {"periodo": "2022T4", "valor": 1000},
            {"periodo": "2023T1", "valor": 1010},
            {"periodo": "2023T2", "valor": 1010},
            {"periodo": "2023T3", "valor": 1010},
            {"periodo": "2023T4", "valor": 1010},
        ])
        crescimento = extrair_crescimento_cvm(dados)
        assert crescimento is not None
        assert abs(crescimento) < 0.02  # ~1% — praticamente estável
