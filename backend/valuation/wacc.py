from typing import Optional

# Prêmio de risco cambial pleno (dívida 100% em moeda estrangeira) — mesma
# ORDEM DE GRANDEZA do "Country Risk Premium" já usado no CAPM
# (valuation/capm.py::calcular_capm(), country_risk = 0.025 = 2.5%).
# Premissa: dívida em moeda estrangeira sem receita em moeda estrangeira
# equivalente carrega o mesmo risco de desvalorização/país que o CAPM já
# precifica pro lado do equity — reaproveitar essa magnitude em vez de
# inventar uma constante nova mantém as duas pernas do custo de capital
# (Ke via CAPM, Kd via WACC) calibradas de forma consistente entre si.
# Referência qualitativa: o spread histórico entre captação corporativa
# brasileira em USD (high-yield) e em BRL de risco equivalente tipicamente
# fica na faixa de 1,5-3 p.p., o que bate com essa ordem de grandeza — não
# é uma calibração econométrica formal, é uma aproximação documentada,
# proporcional à fração da dívida efetivamente exposta (não plena, ver
# calcular_spread_cambial).
PREMIO_RISCO_CAMBIAL_PLENO = 0.025


def calcular_spread_cambial(pct_divida_moeda_estrangeira: Optional[float]) -> float:
    """
    Spread adicional no custo da dívida (Kd) proporcional à fração da
    dívida BRUTA em moeda estrangeira (0-100, mesma escala de
    cvm_provider.py::buscar_saude_financeira_cvm()['pct_divida_moeda_estrangeira']).
    0% de dívida em moeda estrangeira -> spread 0. 100% -> spread pleno
    (PREMIO_RISCO_CAMBIAL_PLENO). None (dado indisponível) -> 0, nunca
    penaliza uma empresa por falta de dado.
    """
    if not pct_divida_moeda_estrangeira:
        return 0.0
    fracao = max(0.0, min(pct_divida_moeda_estrangeira, 100.0)) / 100.0
    return fracao * PREMIO_RISCO_CAMBIAL_PLENO


def calcular_wacc(dados: dict, taxa_capm: float, pct_divida_moeda_estrangeira: Optional[float] = None) -> float:
    """
    Calcula o WACC dinâmico usando dados do provedor e a taxa CAPm calculada.

    `pct_divida_moeda_estrangeira`: % (0-100) da dívida bruta em moeda
    estrangeira, vindo de cvm_provider.py via main.py — adiciona um spread
    ao custo da dívida (Kd) proporcional a essa exposição, ver
    calcular_spread_cambial(). Opcional — None ou 0 mantém o Kd exatamente
    como antes (Selic + 3%, sem ajuste cambial).
    """
    # 1. Obter valores básicos
    preco_atual = dados["preco_atual"]
    num_acoes = dados["num_acoes"]
    
    # Capital Próprio (Market Cap)
    equity = preco_atual * num_acoes
    
    # Capital de Terceiros (Puxar do provedor ou usar aproximação via Dívida Líquida)
    # Se o Fundamentus não der a Dívida Bruta pura, usamos a Dívida Líquida como proxy de mercado
    divida = max(0, dados.get("div_liquida", 0)) 
    
    valor_total = equity + divida
    
    if valor_total == 0:
        return 0.12 # Fallback seguro caso falte dados de balanço
        
    # Pesos
    peso_equity = equity / valor_total
    peso_divida = divida / valor_total
    
    # 2. Custo da Dívida (Kd) 
    # Estimativa de mercado baseada no risco país + Selic. 
    # Uma premissa conservadora é que as empresas captam a Selic + Spread médio de 3%
    selic_atual = dados.get("selic", 0.145) # Ex: 14.50% conforme seu relatório
    spread_cambial = calcular_spread_cambial(pct_divida_moeda_estrangeira)
    custo_divida_kd = selic_atual + 0.03 + spread_cambial
    
    # 3. Benefício Fiscal (Tax Shield) no Brasil = 34%
    imposto_corporativo = 0.34
    
    # 4. Cálculo Final
    wacc = (peso_equity * taxa_capm) + (peso_divida * custo_divida_kd * (1 - imposto_corporativo))
    
    # Limites de segurança para evitar distorções no DCF
    return max(0.08, min(wacc, 0.20))