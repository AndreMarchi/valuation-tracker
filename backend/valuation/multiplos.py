def classificacao_agregada_multiplos(classificacao_pl: str, classificacao_pvp: str) -> str:
    """
    Combina as classificações de P/L e P/VP numa classificação geral —
    usada tanto aqui (estado inicial) quanto em valuation/setor.py::
    aplicar_restricoes_setor() (recalculada após uma eventual restrição de
    setor zerar pl/pvp pra "Não aplicável", pra não ficar com um valor
    agregado desatualizado, ex: setor "Tecnologia" invalida P/VP).
    """
    validas = [c for c in (classificacao_pl, classificacao_pvp) if c != "Não aplicável"]
    if not validas:
        return "Não aplicável"
    if all(c == "Descontada" for c in validas):
        return "Descontada"
    if all(c == "Cara" for c in validas):
        return "Cara"
    # Sinal misto (ex: PL descontado + PVP caro, ou um dos dois "Neutra") —
    # não há alinhamento total nem oposição total, tratado como Neutra.
    return "Neutra"


def calcular_multiplos(pl_atual: float, pvp_atual: float,
                        pl_medio_historico: float, pvp_medio_historico: float,
                        preco_atual: float) -> dict:
    """
    Avalia uma ação pelos múltiplos P/L e P/VP comparando com
    a média histórica da própria empresa.

    Args:
        pl_atual: Preço/Lucro atual da ação
        pvp_atual: Preço/Valor Patrimonial atual
        pl_medio_historico: Média histórica do P/L da empresa
        pvp_medio_historico: Média histórica do P/VP da empresa
        preco_atual: Preço atual da ação

    Returns:
        Dicionário com análise de P/L, P/VP e classificação geral
    """

    if pl_atual <= 0 or pl_medio_historico <= 0:
        classificacao_pl = "Não aplicável"
        desconto_pl = None
    else:
        desconto_pl = ((pl_medio_historico - pl_atual) / pl_medio_historico) * 100
        if desconto_pl >= 20:
            classificacao_pl = "Descontada"
        elif desconto_pl >= 0:
            classificacao_pl = "Neutra"
        else:
            classificacao_pl = "Cara"

    if pvp_atual <= 0 or pvp_medio_historico <= 0:
        classificacao_pvp = "Não aplicável"
        desconto_pvp = None
    else:
        desconto_pvp = ((pvp_medio_historico - pvp_atual) / pvp_medio_historico) * 100
        if desconto_pvp >= 20:
            classificacao_pvp = "Descontada"
        elif desconto_pvp >= 0:
            classificacao_pvp = "Neutra"
        else:
            classificacao_pvp = "Cara"

    # Classificação agregada (P/L + P/VP) — usada pelo pilar "patrimonial_multiplos"
    # da Matriz de Consenso em main.py. Achado real: essa chave nunca existiu
    # no dict de retorno (só as classificações aninhadas de pl/pvp), então o
    # pilar sempre lia "" via .get("classificacao") e caía em "Não aplicável"
    # pra QUALQUER ticker, não só setores com restrição — bug pré-existente,
    # não relacionado à restrição de setor. Ver CONTEXT.md.
    classificacao_geral = classificacao_agregada_multiplos(classificacao_pl, classificacao_pvp)

    return {
        "preco_atual": preco_atual,
        "classificacao": classificacao_geral,
        "pl": {
            "valor": pl_atual,
            "media_historica": pl_medio_historico,
            "desconto": round(desconto_pl, 2) if desconto_pl is not None else None,
            "classificacao": classificacao_pl,
        },
        "pvp": {
            "valor": pvp_atual,
            "media_historica": pvp_medio_historico,
            "desconto": round(desconto_pvp, 2) if desconto_pvp is not None else None,
            "classificacao": classificacao_pvp,
        },
    }