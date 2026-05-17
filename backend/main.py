from fastapi import FastAPI, HTTPException
from dados.provider import buscar_dados
from valuation.graham   import calcular_graham
from valuation.bazin    import calcular_bazin
from valuation.multiplos import calcular_multiplos
from valuation.dcf      import calcular_dcf
from valuation.score    import calcular_score
from valuation.risco import analisar_risco
from dados.historico import buscar_historico_5a, gerar_alertas_historicos
from valuation.setor import aplicar_restricoes_setor
from valuation.endividamento import analisar_endividamento

app = FastAPI(
    title="Valuation Tracker API",
    description="API de análise fundamentalista de ações da B3",
    version="1.0.0",
)

@app.get("/")
async def root():
    return {"status": "ok", "mensagem": "Valuation Tracker API funcionando!"}

@app.get("/cache/clear")
def clear_cache():
    """Limpa o cache em memória."""
    from dados.provider import _cache
    _cache.clear()
    return {"mensagem": "Cache limpo com sucesso"}

@app.get("/valuation/{ticker}")
async def valuation(ticker: str):
    """
    Retorna o valuation completo de uma ação pelo ticker.
    """
    ticker_upper = ticker.upper()

    try:
        dados = buscar_dados(ticker_upper)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar dados: {str(e)}")

    # Extração de dados básicos
    preco   = dados["preco_atual"]
    lpa     = dados["lpa"]
    vpa     = dados["vpa"]
    pl      = dados["pl"]
    pvp     = dados["pvp"]
    div     = dados["dividendo_anual"]
    fcl     = (dados["fluxo_caixa"] or 0) / 1_000_000
    acoes   = (dados["num_acoes"]   or 0) / 1_000_000
    setor   = dados["setor"]

    # --- 1. PREPARAÇÃO DE TAXAS E INDICADORES ---
    
    # Médias históricas — por enquanto dinâmicas simplificadas
    pl_historico  = pl  * 1.2 if pl  else 10.0
    pvp_historico = pvp * 1.2 if pvp else 1.5

    # Cálculo da Taxa de Crescimento (Necessário definir antes do DCF)
    crescimento_historico = dados.get("crescimento_receita_5a", 0) or 0
    # Limites de segurança: entre -5% e 15%
    taxa_crescimento = max(-0.05, min(crescimento_historico, 0.15))
    if taxa_crescimento == 0:
        taxa_crescimento = 0.05

    # Setores cíclicos — limitar crescimento a 8% máximo
    SETORES_CICLICOS = {
        "Transporte Aéreo", "Transporte",
        "Alimentos", "Mineração", "Siderurgia e Metalurgia",
    }
    if dados["setor"] in SETORES_CICLICOS:
        taxa_crescimento = min(taxa_crescimento, 0.08)
        print(f"  setor cíclico — crescimento limitado a {taxa_crescimento}")

    # Taxa de desconto ajustada pelo endividamento  ← ADICIONE AQUI
    div_ebit = (dados.get("div_liquida", 0) or 0) / (dados.get("ebit_12m", 1) or 1)
    if div_ebit > 5:
        taxa_desconto = 0.15
    elif div_ebit > 3:
        taxa_desconto = 0.13
    else:
        taxa_desconto = 0.12

    print(f"  div_ebit={div_ebit:.1f} | taxa_desconto={taxa_desconto}")

    # --- 2. AJUSTE DE FCL POR SETOR (Capex/Dívida) ---
    FATOR_FCL_POR_SETOR = {
        "Alimentos":                       0.4,
        "Alimentos Processados":           0.4,
        "Petróleo, Gás e Biocombustíveis": 0.3,
        "Energia Elétrica":                0.5,
        "Construção Civil":                0.6,
        "Siderurgia e Metalurgia":         0.4,
        "Mineração":                       0.4,
        "Tecnologia":                      0.9,
        "Varejo":                          0.8,
        "Intermediários Financeiros":      0.0,
        "Transporte Aéreo": 0.15,  # capex muito alto + dívida estrutural
        "Transporte":       0.30,
    }
    
    fator_fcl = FATOR_FCL_POR_SETOR.get(setor, 0.7)
    fcl_ajustado = fcl * fator_fcl

    # Log de debug para acompanhamento no terminal
    print(f"DEBUG {ticker_upper}: setor={setor} | fator_fcl={fator_fcl}")
    print(f"  lpa={lpa} | vpa={vpa} | fcl_original={fcl:.2f} | fcl_ajustado={fcl_ajustado:.2f}")

    # --- 3. EXECUÇÃO DOS MÉTODOS DE VALUATION ---
    
    graham    = calcular_graham(lpa, vpa, preco)
    bazin     = calcular_bazin(div, preco)
    multiplos = calcular_multiplos(pl, pvp, pl_historico, pvp_historico, preco)

    if fcl_ajustado > 0 and acoes > 0:
        dcf = calcular_dcf(
            fluxo_caixa_atual=fcl_ajustado,
            taxa_crescimento=taxa_crescimento,
            taxa_desconto=taxa_desconto,
            anos_projecao=5,
            taxa_crescimento_perpetuidade=0.03,
            num_acoes=acoes,
            preco_atual=preco,
        )
    else:
        dcf = {
            "erro": "DCF não aplicável — fluxo de caixa insuficiente ou setor financeiro",
            "valor_intrinseco": None,
            "margem_seguranca": None,
            "classificacao": "Não aplicável",
            "cenarios": None,
        }

    # --- 4. FILTROS E SCORE FINAL ---

    # Aplica restrições específicas por setor (ex: ignora Bazin para Growth)
    graham, bazin, multiplos, dcf, config_setor = aplicar_restricoes_setor(
        setor=setor,
        graham=graham,
        bazin=bazin,
        multiplos=multiplos,
        dcf=dcf,
        ticker=ticker_upper, 
    )

    score = calcular_score(graham, bazin, multiplos, dcf)
    
    risco = analisar_risco(
        ticker=ticker_upper,
        setor=setor,
        score_atual=score["score"],
    )
    
    endividamento = analisar_endividamento(
        div_liquida = dados.get("div_liquida", 0) or 0,
        ebit_12m    = dados.get("ebit_12m", 0) or 0,
        patrim_liq  = dados.get("fluxo_caixa", 0) or 0, # Usando proxy disponível
        score_atual = score["score"],
    )

    # Histórico e alertas contextuais
    historico = buscar_historico_5a(ticker_upper)
    alertas_historicos = gerar_alertas_historicos(historico, dcf, graham, bazin)

    return {
        "ticker":    ticker_upper,
        "nome":      dados["nome"],
        "preco_atual": preco,
        "graham":    graham,
        "bazin":     bazin,
        "multiplos": multiplos,
        "dcf":       dcf,
        "score":     score,
        "risco":     risco,
        "historico_5a":       historico,
        "alertas_historicos": alertas_historicos,
        "setor_info": {
            "setor":          setor,
            "metodos_validos": config_setor["metodos_validos"],
            "metricas_ideais": config_setor["metricas_ideais"],
        },
        "endividamento": endividamento,
    }