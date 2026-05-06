import math


def calcular_graham(lpa: float, vpa: float, preco_atual: float) -> dict:
    """
    Calcula o preço justo de uma ação pelo método Graham.

    Fórmula: √(22,5 × LPA × VPA)

    Args:
        lpa: Lucro Por Ação
        vpa: Valor Patrimonial Por Ação
        preco_atual: Preço atual da ação na bolsa

    Returns:
        Dicionário com preço justo, margem de segurança e classificação
    """

    if lpa <= 0 or vpa <= 0:
        return {
            "erro": "Graham não se aplica a empresas com LPA ou VPA negativos",
            "preco_justo": None,
            "margem_seguranca": None,
            "classificacao": "Não aplicável",
        }

    preco_justo = math.sqrt(22.5 * lpa * vpa)
    margem_seguranca = ((preco_justo - preco_atual) / preco_atual) * 100

    if margem_seguranca >= 20:
        classificacao = "Descontada"
    elif margem_seguranca >= 0:
        classificacao = "Neutra"
    else:
        classificacao = "Cara"

    return {
        "preco_justo": round(preco_justo, 2),
        "preco_atual": preco_atual,
        "margem_seguranca": round(margem_seguranca, 2),
        "classificacao": classificacao,
    }