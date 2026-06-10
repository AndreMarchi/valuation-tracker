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


def calcular_score(
    graham: dict,
    bazin: dict,
    multiplos: dict,
    dcf: dict,
    score_cvm: float,              # Score 0-10 de saude_financeira.py
    lucro_liquido_recente: float,  # Último lucro líquido trimestral real
    fco_recente: float,            # Último FCO trimestral real
    subsetor: str = "Geral"        # Parâmetro opcional para pesos dinâmicos
) -> dict:
    """
    Calcula o Score de Atratividade combinando os métodos de valuation e aplicando
    pesos dinâmicos baseados no subsetor da empresa, além de travas contra Value Traps.
    """
    metodos_pontos = {
        "graham":   _classificacao_para_pontos(graham.get("classificacao")),
        "bazin":    _classificacao_para_pontos(bazin.get("classificacao")),
        "pl":       _classificacao_para_pontos(multiplos["pl"].get("classificacao")),
        "pvp":      _classificacao_para_pontos(multiplos["pvp"].get("classificacao")),
        "dcf":      _classificacao_para_pontos(dcf.get("classificacao")),
    }

    # 1. Busca os pesos dinâmicos baseados no modelo de negócio do subsetor
    pesos = obter_pesos_setoriais(subsetor)

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
            "detalhes": metodos_pontos,
        }

    # Score matemático balanceado pelos pesos do setor
    score = soma_produtos / soma_pesos_validos
    parecer = "Ativo apresenta múltiplos e indicadores em níveis saudáveis de valuation."

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

    score_final = round(score, 1)

    # 6. Definição da Classificação Corrigida
    if score_cvm <= 3.0:
        classificacao = "Risco Elevado / Turnaround"
    elif score_final >= 8:
        classificacao = "Muito Atrativa"
    elif score_final >= 6:
        classificacao = "Atrativa"
    elif score_final >= 4:
        classificacao = "Neutra"
    else:
        classificacao = "Cara / Evitar"

    return {
        "score": score_final,
        "classificacao": classificacao,
        "parecer_analista": parecer,
        "metodos_aplicados": metodos_contados,
        "score_cvm_referencia": score_cvm,
        "detalhes": metodos_pontos,
    }