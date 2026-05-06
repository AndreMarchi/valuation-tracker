from valuation.graham import calcular_graham
from valuation.bazin import calcular_bazin
from valuation.multiplos import calcular_multiplos
from valuation.dcf import calcular_dcf


def _classificacao_para_pontos(classificacao: str) -> float:
    """Converte classificação em pontos."""
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
) -> dict:
    """
    Calcula o Score de Atratividade combinando os 4 métodos de valuation.
    Métodos não aplicáveis são ignorados na média.

    Returns:
        Dicionário com score (0-10), classificação geral e detalhes por método
    """

    metodos = {
        "graham":   _classificacao_para_pontos(graham.get("classificacao")),
        "bazin":    _classificacao_para_pontos(bazin.get("classificacao")),
        "pl":       _classificacao_para_pontos(multiplos["pl"].get("classificacao")),
        "pvp":      _classificacao_para_pontos(multiplos["pvp"].get("classificacao")),
        "dcf":      _classificacao_para_pontos(dcf.get("classificacao")),
    }

    # Ignora métodos não aplicáveis
    pontos_validos = [v for v in metodos.values() if v is not None]

    if not pontos_validos:
        return {
            "score": 0.0,
            "classificacao": "Não aplicável",
            "detalhes": metodos,
        }

    score = round(sum(pontos_validos) / len(pontos_validos), 1)

    if score >= 8:
        classificacao = "Muito Atrativa"
    elif score >= 6:
        classificacao = "Atrativa"
    elif score >= 4:
        classificacao = "Neutra"
    else:
        classificacao = "Cara / Evitar"

    return {
        "score": score,
        "classificacao": classificacao,
        "metodos_aplicados": len(pontos_validos),
        "detalhes": metodos,
    }