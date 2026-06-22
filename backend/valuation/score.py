# backend/valuation/score.py
from valuation.graham import calcular_graham
from valuation.bazin import calcular_bazin
from valuation.multiplos import calcular_multiplos
from valuation.dcf import calcular_dcf
from valuation.setor import obter_pesos_setoriais

def _classificacao_para_pontos(classificacao: str) -> float:
    """Converte classificação em pontos econômicos."""
    return {
        "Descontada":    10.0,
        "Neutra":         5.0,
        "Cara":           0.0,
        "Não aplicável":  None,
    }.get(classificacao, None)

def _safe_float(valor, padrao=0.0):
    """Garante que o valor seja um número, evitando crashes com NoneTypes."""
    if valor is None:
        return padrao
    try:
        return float(valor)
    except (ValueError, TypeError):
        return padrao

def calcular_score(
    graham: dict,
    bazin: dict,
    multiplos: dict,
    dcf: dict,
    score_cvm: float,              
    lucro_liquido_recente: float,  
    fco_recente: float,            
    subsetor: str = "Geral",
    tendencia_receita: str = "estável",
    qualidade_lucro: float = 1.0       
) -> dict:
    
    metodos_pontos = {
        "graham":   _classificacao_para_pontos(graham.get("classificacao")),
        "bazin":    _classificacao_para_pontos(bazin.get("classificacao")),
        "pl":       _classificacao_para_pontos(multiplos["pl"].get("classificacao")),
        "pvp":      _classificacao_para_pontos(multiplos["pvp"].get("classificacao")),
        "dcf":      _classificacao_para_pontos(dcf.get("classificacao")),
    }

    # 1. Busca os pesos dinâmicos baseados no modelo de negócio do subsetor
    pesos = obter_pesos_setoriais(subsetor)

    # 👇 A CORREÇÃO ESTÁ AQUI: Inicialização das variáveis antes do loop 👇
    soma_produtos = 0.0
    soma_pesos_validos = 0.0
    metodos_contados = 0

    # 2. Cálculo da Média Ponderada Inteligente
    for nome_metodo, pontos in metodos_pontos.items():
        if pontos is not None:
            peso_metodo = pesos.get(nome_metodo, 0.2)
            soma_produtos += pontos * peso_metodo
            soma_pesos_validos += peso_metodo
            metodos_contados += 1

    if soma_pesos_validos == 0:
        return {
            "score": 0.0,
            "classificacao": "Não aplicável",
            "parecer_analista": "Não foi possível aplicar nenhum método de valuation válido.",
            "alertas_criticos": [],
            "detalhes": metodos_pontos,
        }

    # Score matemático balanceado pelos pesos do setor
    score = soma_produtos / soma_pesos_validos
    parecer = "Ativo apresenta múltiplos e indicadores em níveis saudáveis de valuation."
    alertas_criticos = []

    # 3. TRAVA DE SEGURANÇA 1: Saúde Financeira Crítica (Filtro K.O.)
    if score_cvm <= 3.0:
        score = min(score, 3.0)
        parecer = "Atenção: Embora os múltiplos pareçam descontados, a saúde financeira via CVM é crítica. Alto risco de Value Trap."
        
    # 4. TRAVA DE SEGURANÇA 2: Operação em Prejuízo Recorrente
    elif lucro_liquido_recente < 0:
        score = max(score - 2.5, 0.0)
        parecer = "Empresa operando em prejuízo nos últimos períodos. Modelos de Valuation tradicionais sofrem distorções."

    # 5. TRAVA DE SEGURANÇA 3: Divergência de Caixa (Queima de FCO)
    if fco_recente < 0 and lucro_liquido_recente < 0:
        score = max(score - 1.5, 0.0)
        parecer += " Perigo: Operação queimando caixa líquido (FCO negativo)."

    # =================================================================
    # 7. NOVAS PENALIDADES DE MOMENTUM (FILTRO ANTI-VALUE TRAP)
    # =================================================================
    
    if tendencia_receita == "caindo":
        score = max(score - 1.0, 0.0)
        alertas_criticos.append("⚠ Receita em queda estrutural nos últimos trimestres.")
        parecer = "Atenção: A empresa está encolhendo operacionalmente. Pode ser uma armadilha de valor."

    if qualidade_lucro is not None and qualidade_lucro < 0.6:
        score = max(score - 1.5, 0.0)
        alertas_criticos.append(f"⚠ Baixa conversão de lucro em caixa (FCO/Lucro = {qualidade_lucro}x).")
        parecer = "Alerta Contábil: O lucro da DRE não está se transformando em dinheiro no caixa."

    # Se a saúde financeira CVM rebaixou o ativo antes, preserva o alerta mais grave
    if score_cvm <= 3.0:
        alertas_criticos.append("⚠ Saúde financeira crítica (Score CVM ≤ 3.0). Alto risco de insolvência.")
        
    if not alertas_criticos and score >= 6:
        alertas_criticos.append("✅ Nenhum alerta crítico operacional identificado.")

    score_final = round(score, 1)

    # 6. Definição da Classificação Corrigida
    if score_cvm <= 3.0 or score_final < 4:
        classificacao = "Risco Elevado / Evitar"
    elif score_final >= 8:
        classificacao = "Muito Atrativa / Alta Convicção"
    elif score_final >= 6:
        classificacao = "Atrativa"
    else:
        classificacao = "Neutra"

    return {
        "score": score_final,
        "classificacao": classificacao,
        "parecer_analista": parecer,
        "alertas_criticos": alertas_criticos, 
        "metodos_aplicados": metodos_contados,
        "score_cvm_referencia": score_cvm,
        "detalhes": metodos_pontos,
    }

def gerar_drivers_valuation(dados_empresa: dict) -> dict:
    """
    Analisa os dados já calculados e extrai os principais drivers positivos e negativos 
    de forma 100% determinística e blindada contra valores nulos.
    """
    positivos = []
    negativos = []

    # 1. Análise Graham
    graham_margem = _safe_float(dados_empresa.get("graham", {}).get("margem_seguranca"))
    if graham_margem > 20:
        positivos.append(f"Graham fortemente descontado (+{graham_margem:.1f}%)")
    elif graham_margem < -10:
        negativos.append(f"Preço acima do VPA/LPA aceitável por Graham ({graham_margem:.1f}%)")

    # 2. Análise de EV/EBITDA
    ev_ebitda_atual = _safe_float(dados_empresa.get("ev_ebitda", {}).get("ev_ebitda_atual"))
    ev_ebitda_medio = _safe_float(dados_empresa.get("ev_ebitda", {}).get("ev_ebitda_medio"))
    
    if 0 < ev_ebitda_atual < ev_ebitda_medio:
        desconto = ((ev_ebitda_medio - ev_ebitda_atual) / ev_ebitda_medio) * 100
        positivos.append(f"EV/EBITDA negociado com {desconto:.1f}% de desconto frente ao histórico")
    elif ev_ebitda_atual > (ev_ebitda_medio * 1.2) and ev_ebitda_medio > 0:
        negativos.append("Múltiplo EV/EBITDA esticado em relação à própria média")
    elif ev_ebitda_atual < 0:
        negativos.append("Geração de caixa operacional negativa (EBITDA < 0)")

    # 3. Dividendos e Bazin
    dy_atual = _safe_float(dados_empresa.get("bazin", {}).get("dividend_yield"))
    if dy_atual >= 6.0:
        positivos.append(f"Dividend Yield robusto ({dy_atual:.2f}%)")

    # 4. Saúde Financeira e Dívida
    divida_ebit = _safe_float(dados_empresa.get("endividamento", {}).get("div_liquida_ebit"))
    if divida_ebit > 3.0:
        negativos.append(f"Alavancagem alta (Dívida Líq/EBIT = {divida_ebit:.1f}x)")
    elif 0 <= divida_ebit < 1.5:
        positivos.append("Baixa alavancagem financeira (caixa confortável)")

    # 5. Análise DCF
    dcf_margem = _safe_float(dados_empresa.get("dcf", {}).get("margem_seguranca"))
    if dcf_margem > 15:
        positivos.append(f"DCF indica subavaliação (+{dcf_margem:.1f}% de margem)")
    elif dcf_margem < -15:
        negativos.append("DCF aponta para sobreavaliação severa nos fluxos futuros")

    return {
        "positivos": positivos,
        "negativos": negativos
    }

