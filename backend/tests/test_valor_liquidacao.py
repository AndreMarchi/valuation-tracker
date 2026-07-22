import pytest

from valor_liquidacao import HaircutsAtivos, calcular_valor_liquidacao

# Balanço sintético conhecido (R$ mil, mas a função é agnóstica de escala —
# só precisa que tudo esteja na mesma unidade entre si):
#   Caixa e Equivalentes:        1.000
#   Aplicações Financeiras:        500
#   Contas a Receber:            2.000
#   Estoques:                    1.500
#   Imobilizado:                 4.000
#   Intangível:                  1.000
#   Passivo Total:               3.000
#   Num. Ações:                    100
BALANCO_SINTETICO = dict(
    caixa_equivalentes=1000.0,
    aplicacoes_financeiras=500.0,
    contas_a_receber=2000.0,
    estoques=1500.0,
    imobilizado=4000.0,
    intangivel=1000.0,
    passivo_total=3000.0,
    num_acoes=100.0,
)

# Ativos ajustados esperados com os haircuts DEFAULT:
#   Caixa:        1000 * 1.00 = 1000.0
#   Aplicações:    500 * 0.90 =  450.0
#   Receber:      2000 * 0.80 = 1600.0
#   Estoques:     1500 * 0.70 = 1050.0
#   Imobilizado:  4000 * 0.50 = 2000.0
#   Intangível:   1000 * 0.00 =    0.0
#   TOTAL AJUSTADO:                6100.0
# Valor de liquidação = 6100 - 3000 (passivo) - 0 (contingências) = 3100.0
# Por ação = 3100 / 100 = 31.0


def test_ativos_ajustados_calculados_passo_a_passo_com_haircuts_default():
    resultado = calcular_valor_liquidacao(**BALANCO_SINTETICO)
    ativos = resultado["ativos_ajustados"]
    assert ativos["caixa_equivalentes"] == pytest.approx(1000.0)
    assert ativos["aplicacoes_financeiras"] == pytest.approx(450.0)
    assert ativos["contas_a_receber"] == pytest.approx(1600.0)
    assert ativos["estoques"] == pytest.approx(1050.0)
    assert ativos["imobilizado"] == pytest.approx(2000.0)
    assert ativos["intangivel"] == pytest.approx(0.0)
    assert resultado["total_ativos_ajustados"] == pytest.approx(6100.0)


def test_valor_liquidacao_total_subtrai_passivo_e_contingencias_zero_por_padrao():
    resultado = calcular_valor_liquidacao(**BALANCO_SINTETICO)
    assert resultado["passivo_total"] == pytest.approx(3000.0)
    assert resultado["contingencias"] == pytest.approx(0.0)
    assert resultado["contingencias_informadas"] is False
    assert resultado["valor_liquidacao_total"] == pytest.approx(3100.0)


def test_valor_liquidacao_por_acao():
    resultado = calcular_valor_liquidacao(**BALANCO_SINTETICO)
    assert resultado["valor_liquidacao_por_acao"] == pytest.approx(31.0)


def test_patrimonio_liquido_negativo_em_liquidacao_false_no_caso_base():
    resultado = calcular_valor_liquidacao(**BALANCO_SINTETICO)
    assert resultado["patrimonio_liquido_negativo_em_liquidacao"] is False


# ─── contingências: input manual opcional, nunca estimado arbitrariamente ───

def test_contingencias_informadas_sao_subtraidas_do_valor_final():
    resultado = calcular_valor_liquidacao(**BALANCO_SINTETICO, contingencias=600.0)
    assert resultado["contingencias"] == pytest.approx(600.0)
    assert resultado["contingencias_informadas"] is True
    # 6100 (ativos ajustados) - 3000 (passivo) - 600 (contingências) = 2500
    assert resultado["valor_liquidacao_total"] == pytest.approx(2500.0)


def test_contingencias_none_nao_e_confundido_com_contingencias_zero_explicito():
    """contingencias=None (ausente) e contingencias=0.0 (confirmado zero)
    produzem o mesmo VALOR, mas o flag informativo tem que diferenciar —
    None não pode ser silenciosamente tratado como 'confirmado sem passivo
    contingente', só como 'não informado'."""
    sem_info = calcular_valor_liquidacao(**BALANCO_SINTETICO, contingencias=None)
    zero_explicito = calcular_valor_liquidacao(**BALANCO_SINTETICO, contingencias=0.0)

    assert sem_info["valor_liquidacao_total"] == zero_explicito["valor_liquidacao_total"]
    assert sem_info["contingencias_informadas"] is False
    assert zero_explicito["contingencias_informadas"] is True


# ─── haircuts customizados: parametrizáveis, não hardcoded ──────────────────

def test_haircuts_customizados_sao_respeitados():
    haircuts_conservadores = HaircutsAtivos(
        caixa_equivalentes=1.0,
        aplicacoes_financeiras=0.5,
        contas_a_receber=0.5,
        estoques=0.3,
        imobilizado=0.2,
        intangivel=0.0,
    )
    resultado = calcular_valor_liquidacao(**BALANCO_SINTETICO, haircuts=haircuts_conservadores)
    # Caixa:       1000 * 1.0 = 1000.0
    # Aplicações:   500 * 0.5 =  250.0
    # Receber:     2000 * 0.5 = 1000.0
    # Estoques:    1500 * 0.3 =  450.0
    # Imobilizado: 4000 * 0.2 =  800.0
    # Intangível:  1000 * 0.0 =    0.0
    # TOTAL:                     3500.0
    assert resultado["total_ativos_ajustados"] == pytest.approx(3500.0)
    assert resultado["haircuts_aplicados"]["imobilizado"] == pytest.approx(0.2)
    # valor de liquidação com haircuts mais duros tem que ser menor que com os defaults
    resultado_default = calcular_valor_liquidacao(**BALANCO_SINTETICO)
    assert resultado["valor_liquidacao_total"] < resultado_default["valor_liquidacao_total"]


def test_haircuts_aplicados_refletem_o_objeto_passado_nao_os_defaults():
    resultado = calcular_valor_liquidacao(**BALANCO_SINTETICO, haircuts=HaircutsAtivos(imobilizado=0.9))
    assert resultado["haircuts_aplicados"]["imobilizado"] == pytest.approx(0.9)
    assert resultado["ativos_ajustados"]["imobilizado"] == pytest.approx(4000.0 * 0.9)


# ─── casos extremos ──────────────────────────────────────────────────────────

def test_passivo_maior_que_ativos_ajustados_da_valor_negativo_nao_clampado():
    """Passivo Total bem acima dos ativos ajustados — o valor de liquidação
    tem que sair NEGATIVO de verdade (não forçado pra 0), sinalizando
    patrimônio líquido negativo numa liquidação forçada."""
    dados = dict(BALANCO_SINTETICO)
    dados["passivo_total"] = 50_000.0
    resultado = calcular_valor_liquidacao(**dados)
    assert resultado["valor_liquidacao_total"] < 0
    assert resultado["valor_liquidacao_por_acao"] < 0
    assert resultado["patrimonio_liquido_negativo_em_liquidacao"] is True


def test_num_acoes_zero_nao_quebra_retorna_valor_por_acao_none():
    dados = dict(BALANCO_SINTETICO)
    dados["num_acoes"] = 0.0
    resultado = calcular_valor_liquidacao(**dados)
    assert resultado["valor_liquidacao_por_acao"] is None
    # o total (agregado, não por ação) continua calculável normalmente
    assert resultado["valor_liquidacao_total"] == pytest.approx(3100.0)


def test_todas_as_classes_de_ativo_zeradas_da_valor_liquidacao_igual_a_menos_passivo():
    resultado = calcular_valor_liquidacao(
        caixa_equivalentes=0.0,
        aplicacoes_financeiras=0.0,
        contas_a_receber=0.0,
        estoques=0.0,
        imobilizado=0.0,
        intangivel=0.0,
        passivo_total=1000.0,
        num_acoes=100.0,
    )
    assert resultado["total_ativos_ajustados"] == pytest.approx(0.0)
    assert resultado["valor_liquidacao_total"] == pytest.approx(-1000.0)
