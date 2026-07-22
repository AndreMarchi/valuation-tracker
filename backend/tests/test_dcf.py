import pytest
from valuation.dcf import calcular_dcf

# Dados base reutilizados nos testes
DADOS_BASE = dict(
    fluxo_caixa_atual=1000.0,
    taxa_crescimento=0.10,
    taxa_desconto=0.12,
    anos_projecao=5,
    taxa_crescimento_perpetuidade=0.03,
    num_acoes=500.0,
    preco_atual=30.0,
)


def test_dcf_retorna_campos_obrigatorios():
    """Resultado deve conter todos os campos esperados."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert "valor_intrinseco" in resultado
    assert "margem_seguranca" in resultado
    assert "classificacao" in resultado
    assert "cenarios" in resultado


def test_dcf_cenarios_presentes():
    """Deve retornar os três cenários: otimista, base e pessimista."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert "otimista" in resultado["cenarios"]
    assert "base" in resultado["cenarios"]
    assert "pessimista" in resultado["cenarios"]


def test_dcf_cenario_otimista_maior_que_base():
    """Cenário otimista deve ser sempre maior que o base."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert resultado["cenarios"]["otimista"] > resultado["cenarios"]["base"]


def test_dcf_cenario_pessimista_menor_que_base():
    """Cenário pessimista deve ser sempre menor que o base."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert resultado["cenarios"]["pessimista"] < resultado["cenarios"]["base"]


def test_dcf_classificacao_valida():
    """Classificação deve ser sempre um dos três valores válidos."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert resultado["classificacao"] in ["Descontada", "Neutra", "Cara"]


def test_dcf_margem_coerente_com_classificacao():
    """Margem de segurança deve ser coerente com a classificação."""
    resultado = calcular_dcf(**DADOS_BASE)
    if resultado["classificacao"] == "Descontada":
        assert resultado["margem_seguranca"] >= 20
    elif resultado["classificacao"] == "Neutra":
        assert 0 <= resultado["margem_seguranca"] < 20
    else:
        assert resultado["margem_seguranca"] < 0


# ─── Enterprise Value -> Equity Value (bug estrutural corrigido) ───────────
# calcular_dcf() descontava o fluxo (baseado em NOPAT, ver valuation/nopat.py)
# à WACC, chegando no valor da EMPRESA inteira (Enterprise Value), mas nunca
# subtraía a dívida líquida antes de dividir por ação — entregava EV/ação
# sendo comparado com preço de equity. Ver CONTEXT.md (achado real: BEEF3,
# Dívida Líquida/EBIT ~3,5x, valor_intrinseco caiu de R$13,99 pra R$0,31).

def test_divida_liquida_zero_e_identico_ao_comportamento_sem_o_parametro():
    """divida_liquida=0.0 (default) não pode mudar nada pra quem já chamava
    a função sem o argumento novo — compatibilidade com todos os testes
    acima, que nunca passaram divida_liquida."""
    resultado_sem_argumento = calcular_dcf(**DADOS_BASE)
    resultado_com_zero_explicito = calcular_dcf(**DADOS_BASE, divida_liquida=0.0)

    assert resultado_sem_argumento["valor_intrinseco"] == resultado_com_zero_explicito["valor_intrinseco"]
    assert resultado_sem_argumento["cenarios"] == resultado_com_zero_explicito["cenarios"]
    assert resultado_sem_argumento["matriz_sensibilidade"] == resultado_com_zero_explicito["matriz_sensibilidade"]


def test_divida_liquida_positiva_reduz_valor_intrinseco_na_proporcao_certa():
    """Com dívida líquida > 0, o valor_intrinseco deve ser estritamente
    menor que o mesmo cálculo sem dívida — na proporção esperada
    (divida_liquida/num_acoes), já que a subtração acontece ANTES da
    divisão por ação, uma única vez, e não afeta a projeção dos fluxos."""
    divida_liquida = 20_000.0  # R$ mi
    num_acoes = DADOS_BASE["num_acoes"]

    sem_divida = calcular_dcf(**DADOS_BASE, divida_liquida=0.0)
    com_divida = calcular_dcf(**DADOS_BASE, divida_liquida=divida_liquida)

    assert com_divida["valor_intrinseco"] < sem_divida["valor_intrinseco"]

    reducao_esperada_por_acao = divida_liquida / num_acoes
    reducao_real = sem_divida["valor_intrinseco"] - com_divida["valor_intrinseco"]
    assert reducao_real == pytest.approx(reducao_esperada_por_acao, abs=0.01)

    # cenários e matriz de sensibilidade usam a mesma _calcular_valor() —
    # devem refletir a subtração automaticamente, não precisam de wiring à parte
    assert com_divida["cenarios"]["otimista"] < sem_divida["cenarios"]["otimista"]
    assert com_divida["cenarios"]["pessimista"] < sem_divida["cenarios"]["pessimista"]
    for linha_sem, linha_com in zip(sem_divida["matriz_sensibilidade"]["linhas"], com_divida["matriz_sensibilidade"]["linhas"]):
        for v_sem, v_com in zip(linha_sem["valores"], linha_com["valores"]):
            assert v_com < v_sem


def test_divida_liquida_negativa_caixa_liquido_aumenta_valor_intrinseco():
    """Empresa com caixa líquido (dívida líquida negativa, ex: WEGE3) deve
    ter o valor por ação AUMENTADO, não reduzido — a subtração de um valor
    negativo soma o caixa de volta ao equity."""
    sem_divida = calcular_dcf(**DADOS_BASE, divida_liquida=0.0)
    com_caixa_liquido = calcular_dcf(**DADOS_BASE, divida_liquida=-5_000.0)

    assert com_caixa_liquido["valor_intrinseco"] > sem_divida["valor_intrinseco"]