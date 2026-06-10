# backend/tests/test_score.py
import pytest
from valuation.score import calcular_score

# Mocks base reutilizáveis com classificações padrão
GRAHAM_DESCONTADO  = {"classificacao": "Descontada"}
BAZIN_DESCONTADO   = {"classificacao": "Descontada"}
DCF_DESCONTADO     = {"classificacao": "Descontada"}
MULTIPLOS_NEUTROS  = {
    "pl":  {"classificacao": "Neutra"},
    "pvp": {"classificacao": "Neutra"},
}

def test_calcular_score_empresa_saudavel():
    """Garante o cálculo da média ponderada padrão sem interferência de travas quando a saúde está boa."""
    # Subsetor padrão "Geral" aplica peso 0.2 para cada um dos 5 métodos.
    # Métodos: Graham(10*0.2) + Bazin(10*0.2) + PL(5*0.2) + PVP(5*0.2) + DCF(10*0.2) = 8.0 / 1.0 = 8.0
    resultado = calcular_score(
        graham=GRAHAM_DESCONTADO,
        bazin=BAZIN_DESCONTADO,
        multiplos=MULTIPLOS_NEUTROS,
        dcf=DCF_DESCONTADO,
        score_cvm=8.5,               # Saúde excelente
        lucro_liquido_recente=150.0, # Lucro positivo
        fco_recente=180.0,           # Gerando caixa operacional
        subsetor="Geral"             # Garante pesos equivalentes (0.2 cada)
    )
    
    assert resultado["score"] == 8.0
    assert resultado["classificacao"] == "Muito Atrativa"
    assert "indicadores em níveis saudáveis" in resultado["parecer_analista"]


def test_calcular_score_inteligencia_setorial_varejo():
    """Garante que o score mude a ponderação se o subsetor for de crescimento/varejo de moda."""
    # Varejo aplica pesos: Graham(0.0), Bazin(0.1), PL(0.3), PVP(0.1), DCF(0.5).
    # Soma pesos válidos: 0.1 + 0.3 + 0.1 + 0.5 = 1.0
    # Produtos: Graham(10*0) + Bazin(10*0.1=1) + PL(5*0.3=1.5) + PVP(5*0.1=0.5) + DCF(10*0.5=5) = 8.0
    resultado = calcular_score(
        graham=GRAHAM_DESCONTADO,
        bazin=BAZIN_DESCONTADO,
        multiplos=MULTIPLOS_NEUTROS,
        dcf=DCF_DESCONTADO,
        score_cvm=8.5,
        lucro_liquido_recente=150.0,
        fco_recente=180.0,
        subsetor="Varejo de Moda"     # Aciona pesos customizados do varejo
    )
    
    assert resultado["score"] == 8.0
    assert resultado["metodos_aplicados"] == 5


def test_calcular_score_ignora_nao_aplicavel():
    """Garante que métodos marcados como 'Não aplicável' fiquem de fora do denominador da média ponderada."""
    graham_nao_aplicavel = {"classificacao": "Não aplicável"}
    
    # Subsetor Geral (peso 0.2 para cada método). Graham fica fora.
    # Soma dos pesos válidos restantes (Bazin, PL, PVP, DCF) = 0.8
    # Produtos: Bazin(10*0.2=2) + PL(5*0.2=1) + PVP(5*0.2=1) + DCF(10*0.2=2) = 6.0
    # Média Ponderada: 6.0 / 0.8 = 7.5
    resultado = calcular_score(
        graham=graham_nao_aplicavel,
        bazin=BAZIN_DESCONTADO,
        multiplos=MULTIPLOS_NEUTROS,
        dcf=DCF_DESCONTADO,
        score_cvm=7.0,
        lucro_liquido_recente=50.0,
        fco_recente=40.0,
        subsetor="Geral"
    )
    
    assert resultado["score"] == 7.5
    assert resultado["metodos_aplicados"] == 4
    assert resultado["classificacao"] == "Atrativa"


def test_trava_filtro_ko_saude_critica_value_trap():
    """Se o Score CVM for menor ou igual a 3, o score final deve ser capado em 3.0 (Caso Casas Bahia)."""
    resultado = calcular_score(
        graham=GRAHAM_DESCONTADO,
        bazin=BAZIN_DESCONTADO,
        multiplos=MULTIPLOS_NEUTROS,
        dcf=DCF_DESCONTADO,
        score_cvm=1.2,                # Trigger da trava (<= 3.0)
        lucro_liquido_recente=-200.0, # Prejuízo
        fco_recente=50.0,
        subsetor="Geral"
    )
    
    assert resultado["score"] == 3.0
    assert resultado["classificacao"] == "Risco Elevado / Turnaround"
    assert "Alto risco de Value Trap" in resultado["parecer_analista"]


def test_trava_penalizacao_por_prejuizo():
    """Se a empresa opera em prejuízo mas a CVM não atingiu o limite crítico, aplica deságio de 2.5 pontos."""
    # Múltiplos calculados em "Geral" dão 8.0. Subtrai penalização de 2.5 -> 5.5
    resultado = calcular_score(
        graham=GRAHAM_DESCONTADO,
        bazin=BAZIN_DESCONTADO,
        multiplos=MULTIPLOS_NEUTROS,
        dcf=DCF_DESCONTADO,
        score_cvm=5.5,               # Regular, não aciona o teto de 3.0
        lucro_liquido_recente=-50.0, # Trigger do prejuízo (< 0)
        fco_recente=30.0,            # FCO ainda positivo
        subsetor="Geral"
    )
    
    assert resultado["score"] == 5.5
    assert resultado["classificacao"] == "Neutra"
    assert "operando em prejuízo" in resultado["parecer_analista"]


def test_trava_queima_de_caixa_operacional():
    """Se a empresa está em prejuízo E queima caixa operacional (FCO < 0), aplica dupla penalização."""
    # Múltiplos base em "Geral" dariam 8.0. Prejuízo (-2.5) + Queima FCO (-1.5) -> 4.0
    resultado = calcular_score(
        graham=GRAHAM_DESCONTADO,
        bazin=BAZIN_DESCONTADO,
        multiplos=MULTIPLOS_NEUTROS,
        dcf=DCF_DESCONTADO,
        score_cvm=4.5,
        lucro_liquido_recente=-80.0, # Prejuízo
        fco_recente=-120.0,          # Queima de caixa operacional
        subsetor="Geral"
    )
    
    assert resultado["score"] == 4.0
    assert "queimando caixa líquido" in resultado["parecer_analista"]


def test_calcular_score_totalmente_invalido():
    """Garante tratamento correto se nenhum pilar matemático puder ser calculado."""
    nao_disp = {"classificacao": "Não aplicável"}
    mult_disp = {"pl": nao_disp, "pvp": nao_disp}
    
    resultado = calcular_score(
        graham=nao_disp,
        bazin=nao_disp,
        multiplos=mult_disp,
        dcf=nao_disp,
        score_cvm=0.0,
        lucro_liquido_recente=0.0,
        fco_recente=0.0,
        subsetor="Geral"
    )
    
    assert resultado["score"] == 0.0
    assert resultado["classificacao"] == "Não aplicável"