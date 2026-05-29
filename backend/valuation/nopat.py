def calcular_fcl_via_nopat(dados: dict) -> float:
    """
    Calcula o Fluxo de Caixa Livre a partir do NOPAT, 
    mantendo a cobertura completa de todos os setores mapeados.
    """
    ebit_12m = dados.get("ebit_12m", 0) or 0
    
    if ebit_12m <= 0:
        return 0.0
        
    # Alíquota padrão corporativa no Brasil (IRPJ + CSLL = 34%)
    taxa_imposto = 0.34
    nopat = ebit_12m * (1 - taxa_imposto)
    
    # Setor retornado pelo provedor de dados
    setor = dados.get("setor", "")
    
    # Fatores calibrados para a partida do EBIT (NOPAT)
    FATOR_CONVERSAO_NOPAT = {
        # Setores de Capex Pesadíssimo e Ciclos Fortes
        "Transporte Aéreo":                0.20,  # Capex brutal + leasing de aeronaves
        "Transporte":                      0.40,  # Renovação de frotas/concessões
        "Petróleo, Gás e Biocombustíveis": 0.45,  # Exploração e refino demandam bilhões
        
        # Setores de Capex Alto
        "Alimentos":                       0.50,  # Complexos frigoríficos e cadeias globais
        "Alimentos Processados":           0.50,  # JBSS3 e BRFS3 entram aqui
        "Siderurgia e Metalurgia":         0.50,  # Altos-fornos e pesados
        "Mineração":                       0.55,  # Infraestrutura de extração e escoamento
        "Construção Civil":                0.60,  # Custo de obras longo e estocagem de terrenos
        
        # Setores de Infraestrutura com Fluxo Previsível
        "Energia Elétrica":                0.60,  # Transmissão/Geração regulada com Capex contínuo
        
        # Setores de Capex Médio a Baixo (Asset-Light)
        "Varejo":                          0.75,  # Giro de estoque rápido
        "Tecnologia":                      0.85,  # Baixa infraestrutura física corporativa
        
        # Setor Financeiro (DCF não aplicável por estrutura de balanço)
        "Intermediários Financeiros":      0.0,
    }
    
    # Fator padrão de 0.65 caso apareça um setor novo não mapeado
    fator = FATOR_CONVERSAO_NOPAT.get(setor, 0.65)
    
    # Transforma o valor bruto para a escala de milhões utilizada no seu main.py
    fcl_real = (nopat * fator) / 1_000_000
    return fcl_real