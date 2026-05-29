def calcular_wacc(dados: dict, taxa_capm: float) -> float:
    """
    Calcula o WACC dinâmico usando dados do provedor e a taxa CAPm calculada.
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
    custo_divida_kd = selic_atual + 0.03 
    
    # 3. Benefício Fiscal (Tax Shield) no Brasil = 34%
    imposto_corporativo = 0.34
    
    # 4. Cálculo Final
    wacc = (peso_equity * taxa_capm) + (peso_divida * custo_divida_kd * (1 - imposto_corporativo))
    
    # Limites de segurança para evitar distorções no DCF
    return max(0.08, min(wacc, 0.20))