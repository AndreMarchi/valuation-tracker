from fastapi import FastAPI, HTTPException
from dados.provider import buscar_dados
from valuation.graham   import calcular_graham
from valuation.bazin    import calcular_bazin
from valuation.multiplos import calcular_multiplos
from valuation.dcf      import calcular_dcf
from valuation.score    import calcular_score
from valuation.risco import analisar_risco

app = FastAPI(
    title="Valuation Tracker API",
    description="API de análise fundamentalista de ações da B3",
    version="1.0.0",
)

@app.get("/")
async def root():
    return {"status": "ok", "mensagem": "Valuation Tracker API funcionando!"}


@app.get("/valuation/{ticker}")
async def valuation(ticker: str):
    """
    Retorna o valuation completo de uma ação pelo ticker.
    Exemplo: /valuation/PETR4
    """

    try:
        dados = buscar_dados(ticker.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar dados: {str(e)}")

    preco   = dados["preco_atual"]
    lpa     = dados["lpa"]
    vpa     = dados["vpa"]
    pl      = dados["pl"]
    pvp     = dados["pvp"]
    div     = dados["dividendo_anual"]
    fcl   = (dados["fluxo_caixa"] or 0) / 1_000_000
    acoes = (dados["num_acoes"]   or 0) / 1_000_000
    #fcl     = dados["fluxo_caixa"] / 1_000_000  # converte para milhões brapi
    #acoes   = dados["num_acoes"]  / 1_000_000

    # Médias históricas — por enquanto fixas, virão do banco futuramente
    pl_historico  = pl  * 1.2 if pl  else 10.0
    pvp_historico = pvp * 1.2 if pvp else 1.5

    graham    = calcular_graham(lpa, vpa, preco)
    bazin     = calcular_bazin(div, preco)
    multiplos = calcular_multiplos(pl, pvp, pl_historico, pvp_historico, preco)

    # DCF requer fluxo de caixa e número de ações válidos
    if fcl > 0 and acoes > 0:
        dcf = calcular_dcf(
            fluxo_caixa_atual=fcl,
            taxa_crescimento=0.08,
            taxa_desconto=0.12,
            anos_projecao=5,
            taxa_crescimento_perpetuidade=0.03,
            num_acoes=acoes,
            preco_atual=preco,
        )
    else:
        dcf = {
            "erro": "DCF não aplicável — fluxo de caixa ou número de ações indisponível",
            "valor_intrinseco": None,
            "margem_seguranca": None,
            "classificacao": "Não aplicável",
            "cenarios": None,
        }

    score = calcular_score(graham, bazin, multiplos, dcf)
    risco = analisar_risco(
        ticker=dados["ticker"],
        setor=dados["setor"],
        score_atual=score["score"],
    )

    return {
        "ticker":    dados["ticker"],
        "nome":      dados["nome"],
        "preco_atual": preco,
        "graham":    graham,
        "bazin":     bazin,
        "multiplos": multiplos,
        "dcf":       dcf,
        "score":     score,
        "risco":       risco,
    }