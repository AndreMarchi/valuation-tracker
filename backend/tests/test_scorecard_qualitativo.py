import pytest

from scorecard_qualitativo import (
    ScorecardQualitativo,
    TETO_AJUSTE_PONTOS,
    calcular_ajuste_qualitativo,
    aplicar_ajuste_ao_score,
)


# ─── ScorecardQualitativo — validação de faixa ──────────────────────────────

def test_defaults_sao_todos_neutros_5():
    s = ScorecardQualitativo()
    assert s.moat == 5.0
    assert s.gestao == 5.0
    assert s.concentracao_clientes == 5.0
    assert s.risco_regulatorio == 5.0
    assert s.poder_precificacao == 5.0


def test_nota_fora_da_faixa_0_10_levanta_erro():
    with pytest.raises(ValueError):
        ScorecardQualitativo(moat=10.1)
    with pytest.raises(ValueError):
        ScorecardQualitativo(gestao=-0.1)


def test_notas_nos_limites_0_e_10_sao_validas():
    s = ScorecardQualitativo(moat=0.0, gestao=10.0, concentracao_clientes=0.0, risco_regulatorio=10.0, poder_precificacao=0.0)
    assert s.moat == 0.0
    assert s.gestao == 10.0


# ─── calcular_ajuste_qualitativo() — casos extremos e mistos ────────────────

def test_todas_as_notas_neutras_5_produz_ajuste_zero():
    resultado = calcular_ajuste_qualitativo(ScorecardQualitativo())
    assert resultado["media_dimensoes"] == pytest.approx(5.0)
    assert resultado["ajuste_pontos"] == pytest.approx(0.0)


def test_todas_as_notas_zero_produz_ajuste_negativo_no_teto():
    scorecard = ScorecardQualitativo(0.0, 0.0, 0.0, 0.0, 0.0)
    resultado = calcular_ajuste_qualitativo(scorecard)
    assert resultado["media_dimensoes"] == pytest.approx(0.0)
    assert resultado["ajuste_pontos"] == pytest.approx(-TETO_AJUSTE_PONTOS)


def test_todas_as_notas_dez_produz_ajuste_positivo_no_teto():
    scorecard = ScorecardQualitativo(10.0, 10.0, 10.0, 10.0, 10.0)
    resultado = calcular_ajuste_qualitativo(scorecard)
    assert resultado["media_dimensoes"] == pytest.approx(10.0)
    assert resultado["ajuste_pontos"] == pytest.approx(TETO_AJUSTE_PONTOS)


def test_notas_mistas_produz_ajuste_proporcional_a_media():
    # média = (8+6+4+2+10)/5 = 6.0 -> ajuste = (6-5)/5 * 1.5 = 0.3
    scorecard = ScorecardQualitativo(moat=8, gestao=6, concentracao_clientes=4, risco_regulatorio=2, poder_precificacao=10)
    resultado = calcular_ajuste_qualitativo(scorecard)
    assert resultado["media_dimensoes"] == pytest.approx(6.0)
    assert resultado["ajuste_pontos"] == pytest.approx(0.3)


def test_ajuste_e_estritamente_monotonico_com_a_media():
    """Scorecard com média maior tem que produzir ajuste estritamente
    maior — confirma que a fórmula é sensível de verdade a cada nota,
    não só aos extremos."""
    baixo = ScorecardQualitativo(3, 3, 3, 3, 3)
    medio = ScorecardQualitativo(5, 5, 5, 5, 5)
    alto = ScorecardQualitativo(7, 7, 7, 7, 7)

    ajuste_baixo = calcular_ajuste_qualitativo(baixo)["ajuste_pontos"]
    ajuste_medio = calcular_ajuste_qualitativo(medio)["ajuste_pontos"]
    ajuste_alto = calcular_ajuste_qualitativo(alto)["ajuste_pontos"]

    assert ajuste_baixo < ajuste_medio < ajuste_alto


def test_teto_ajuste_customizado_e_respeitado():
    """teto_ajuste_pontos é parametrizável — não hardcoded sem override."""
    scorecard = ScorecardQualitativo(10.0, 10.0, 10.0, 10.0, 10.0)
    resultado = calcular_ajuste_qualitativo(scorecard, teto_ajuste_pontos=3.0)
    assert resultado["ajuste_pontos"] == pytest.approx(3.0)
    assert resultado["teto_ajuste_pontos"] == pytest.approx(3.0)


# ─── aplicar_ajuste_ao_score() — nunca domina o resultado quantitativo ──────

def test_score_ajustado_soma_base_mais_ajuste():
    scorecard = ScorecardQualitativo(10.0, 10.0, 10.0, 10.0, 10.0)
    resultado = aplicar_ajuste_ao_score(score_base=5.0, scorecard=scorecard)
    assert resultado["score_base"] == pytest.approx(5.0)
    assert resultado["score_ajustado_qualitativo"] == pytest.approx(5.0 + TETO_AJUSTE_PONTOS)


def test_scorecard_perfeito_nunca_transforma_score_pessimo_em_muito_atrativo():
    """Critério de aceite: o ajuste NUNCA pode dominar o resultado
    quantitativo. Um score_base de 'Cara/Evitar' (ex: 1.0) com o melhor
    scorecard qualitativo POSSÍVEL não pode virar 'Muito Atrativa'
    (>= 8) — só um nudge, nunca um veredito por si só."""
    scorecard_perfeito = ScorecardQualitativo(10.0, 10.0, 10.0, 10.0, 10.0)
    resultado = aplicar_ajuste_ao_score(score_base=1.0, scorecard=scorecard_perfeito)
    assert resultado["score_ajustado_qualitativo"] < 8.0
    assert resultado["score_ajustado_qualitativo"] == pytest.approx(1.0 + TETO_AJUSTE_PONTOS)


def test_scorecard_pessimo_nunca_transforma_score_otimo_em_evitar():
    scorecard_pessimo = ScorecardQualitativo(0.0, 0.0, 0.0, 0.0, 0.0)
    resultado = aplicar_ajuste_ao_score(score_base=9.0, scorecard=scorecard_pessimo)
    assert resultado["score_ajustado_qualitativo"] > 3.0
    assert resultado["score_ajustado_qualitativo"] == pytest.approx(9.0 - TETO_AJUSTE_PONTOS)


def test_score_ajustado_e_clampado_no_teto_superior_10():
    scorecard_perfeito = ScorecardQualitativo(10.0, 10.0, 10.0, 10.0, 10.0)
    resultado = aplicar_ajuste_ao_score(score_base=10.0, scorecard=scorecard_perfeito)
    assert resultado["score_ajustado_qualitativo"] == pytest.approx(10.0)


def test_score_ajustado_e_clampado_no_piso_inferior_0():
    scorecard_pessimo = ScorecardQualitativo(0.0, 0.0, 0.0, 0.0, 0.0)
    resultado = aplicar_ajuste_ao_score(score_base=0.0, scorecard=scorecard_pessimo)
    assert resultado["score_ajustado_qualitativo"] == pytest.approx(0.0)


def test_score_ajustado_neutro_nao_muda_score_base():
    resultado = aplicar_ajuste_ao_score(score_base=6.5, scorecard=ScorecardQualitativo())
    assert resultado["score_ajustado_qualitativo"] == pytest.approx(6.5)
