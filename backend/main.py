# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from dados.provider import buscar_dados
from valuation.graham   import calcular_graham
from valuation.bazin    import calcular_bazin
from valuation.multiplos import calcular_multiplos
from valuation.dcf      import calcular_dcf
from valuation.score    import calcular_score, gerar_drivers_valuation
from valuation.risco import analisar_risco
from dados.historico import buscar_historico_5a, gerar_alertas_historicos
from valuation.setor import aplicar_restricoes_setor, buscar_concorrentes_por_subsetor
from valuation.endividamento import analisar_endividamento
from valuation.capm     import calcular_capm
from valuation.wacc     import calcular_wacc
from valuation.ev_ebitda import calcular_ev_ebitda
from valuation.crescimento import (
    detectar_fase_crescimento,
    calcular_peg_ratio,
    calcular_ev_receita,
    calcular_rule_of_40,
    calcular_dcf_duas_fases,
)
import os
from dados.cvm_provider import buscar_saude_financeira_cvm
from valuation.saude_financeira import calcular_saude_financeira, extrair_crescimento_cvm
from dados.selic import buscar_selic_atual
from valuation.dcf_concessao import (
    calcular_dcf_concessao,
    detectar_concessao,
    empresa_tem_concessao,
    ParametrosConcessao,
)

app = FastAPI(
    title="Valuation Tracker API",
    description="API de análise fundamentalista de ações da B3",
    version="1.0.0",
)

@app.get("/")
async def root():
    # Em produção, serve o index.html do frontend buildado
    static_index = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)
    return {"status": "ok", "mensagem": "Valuation Tracker API funcionando!"}

@app.get("/api/cache/clear")
@app.get("/cache/clear")
def clear_cache():
    """Limpa o cache em memória."""
    from dados.provider import _cache
    _cache.clear()
    return {"mensagem": "Cache limpo com sucesso"}

@app.get("/api/selic")
@app.get("/selic")
def selic_atual():
    """Retorna a taxa Selic atual via BACEN."""
    selic = buscar_selic_atual()
    return {
        "selic_decimal": selic,
        "selic_pct":     round(selic * 100, 2),
    }

@app.get("/api/valuation/{ticker}")
@app.get("/valuation/{ticker}")
async def valuation(ticker: str):
    """
    Retorna o valuation completo de uma ação pelo ticker de forma 100% dinâmica.
    """
    ticker_upper = ticker.upper()

    try:
        dados = buscar_dados(ticker_upper)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar dados: {str(e)}")

    # Extração de dados básicos do provider dinâmico
    preco   = dados.get("preco_atual", 0)
    lpa     = dados.get("lpa", 0)
    vpa     = dados.get("vpa", 0)
    pl      = dados.get("pl", 0)
    pvp     = dados.get("pvp", 0)
    div     = dados.get("dividendo_anual", 0)
    fcl     = (dados.get("fluxo_caixa", 0) or 0) / 1_000_000
    acoes   = (dados.get("num_acoes", 0)   or 0) / 1_000_000
    setor   = dados.get("setor", "Geral")
    subsetor = dados.get("industria", "Geral")

    # --- 1. PREPARAÇÃO DE TAXAS E INDICADORES ---
    
    # Médias históricas dinâmicas simplificadas
    pl_historico  = pl  * 1.2 if pl  else 10.0
    pvp_historico = pvp * 1.2 if pvp else 1.5

    # Inicialização de variáveis de segurança para a trava de risco
    score_cvm_valor = 5.0  # Neutro por padrão se não houver CVM
    lucro_recente_valor = lpa if lpa is not None else 1.0
    fco_recente_valor = fcl

    # ── Saúde Financeira via CVM (não bloqueia se falhar) ──────────────────
    try:
        #dados_cvm = buscar_saude_financeira_cvm(ticker_upper)
        dados_cvm = buscar_saude_financeira_cvm(ticker_upper, dados.get("nome", ""))
        saude_financeira = calcular_saude_financeira(dados_cvm)
        crescimento_cvm = extrair_crescimento_cvm(dados_cvm)
        
        # Coleta das métricas reais para alimentar as novas travas do score.py
        if saude_financeira and "score" in saude_financeira:
            score_cvm_valor = saude_financeira["score"]
            
        # Tenta extrair valores brutos mais recentes se mapeados in dados_cvm
        if dados_cvm and isinstance(dados_cvm, dict):
            lucro_recente_valor = dados_cvm.get("lucro_liquido_recente", lucro_recente_valor)
            fco_recente_valor = dados_cvm.get("fco_recente", fco_recente_valor)
    except Exception:
        saude_financeira = {"disponivel": False}
        crescimento_cvm = None

    # Usa dados CVM quando disponível (mais preciso que Fundamentus 5a)
    crescimento_historico = crescimento_cvm if crescimento_cvm is not None else (dados.get("crescimento_receita_5a", 0) or 0)
    # Limites de segurança: entre -5% e 15%
    taxa_crescimento = max(-0.05, min(crescimento_historico, 0.15))
    if taxa_crescimento == 0:
        taxa_crescimento = 0.05

    # Setores cíclicos — limitar crescimento a 8% máximo
    SETORES_CICLICOS = {
        "Transporte Aéreo", "Transporte",
        "Alimentos", "Mineração", "Siderurgia e Siderurgia e Metalurgia",
    }
    if setor in SETORES_CICLICOS:
        taxa_crescimento = min(taxa_crescimento, 0.08)

    # Se empresa é muito lucrativa mas com crescimento negativo, usa mínimo de 2%
    if taxa_crescimento < 0 and lpa > 0 and vpa > 0:
        taxa_crescimento = 0.02

    # Taxa de desconto pelo CAPM Institucional (Novo formato detalhado)
    selic_val = buscar_selic_atual()
    capm = calcular_capm(
        setor=setor, 
        selic_atual=selic_val, 
        beta_ativo=dados.get("beta", 1.0)
    )
    taxa_capm = capm.get("taxa_desconto", 0.12)

    # Ajuste extra para endividamento alto aplicado dinamicamente no WACC
    div_ebit = (dados.get("div_liquida", 0) or 0) / (dados.get("ebit_12m", 1) or 1)

    # --- CALCULO DO WACC DINÂMICO ---
    taxa_desconto = calcular_wacc(dados, taxa_capm)

    # --- 2. CÁLCULO DO FCL REAL VIA NOPAT ---
    from valuation.nopat import calcular_fcl_via_nopat
    fcl_ajustado = calcular_fcl_via_nopat(dados)
    
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

    # Aplica restrições específicas por setor
    graham, bazin, multiplos, dcf, config_setor = aplicar_restricoes_setor(
        setor=setor,
        graham=graham,
        bazin=bazin,
        multiplos=multiplos,
        dcf=dcf,
        ticker=ticker_upper, 
    )

    # Captura das variáveis de Momentum para injetar no Score Institucional
    tend_rec = saude_financeira.get("tendencia_receita", "estável") if saude_financeira and saude_financeira.get("disponivel") else "estável"
    qual_luc = saude_financeira.get("qualidade_lucro", 1.0) if saude_financeira and saude_financeira.get("disponivel") else 1.0

    score = calcular_score(
        graham=graham,
        bazin=bazin,
        multiplos=multiplos,
        dcf=dcf,
        score_cvm=score_cvm_valor,
        lucro_liquido_recente=lucro_recente_valor,
        fco_recente=fco_recente_valor,
        subsetor=subsetor,
        tendencia_receita=tend_rec,
        qualidade_lucro=qual_luc
    )
    
    # EV/EBITDA Híbrido (Blend 50/50 - Empresa vs Setor)
    historico_ev = dados.get("ev_ebitda_medio_5a") or dados.get("ev_ebitda", 8.0)
    setor_ev = config_setor.get("ev_ebitda_setor", 8.0)

    ev_ebitda = calcular_ev_ebitda(
        ev_ebitda_atual     = dados.get("ev_ebitda", 0) or 0,
        ev_ebitda_historico = historico_ev,
        ev_ebitda_setor     = setor_ev,
        ebit_12m            = dados.get("ebit_12m", 0) or 0,
        num_acoes           = dados.get("num_acoes", 0) or 0,
        div_liquida         = dados.get("div_liquida", 0) or 0,
    )

    risco = analisar_risco(
        ticker=ticker_upper,
        setor=setor,
        score_atual=score.get("score", 0),
    )
    
    endividamento = analisar_endividamento(
        div_liquida = dados.get("div_liquida", 0) or 0,
        ebit_12m    = dados.get("ebit_12m", 0) or 0,
        patrim_liq  = dados.get("fluxo_caixa", 0) or 0,
        score_atual = score.get("score", 0),
    )

    # Análise de crescimento dinâmica
    crescimento_5a = dados.get("crescimento_receita_5a", 0) or 0
    fase_crescimento = detectar_fase_crescimento(crescimento_5a)

    peg = calcular_peg_ratio(pl=pl, crescimento_lucro=crescimento_5a)

    ev_receita = calcular_ev_receita(
        psr_atual=dados.get("psr", 0) or 0,
        setor=setor,
        receita_12m=dados.get("receita_liquida_12m", 0) or 0,
        num_acoes=dados.get("num_acoes", 0) or 0,
        div_liquida=dados.get("div_liquida", 0) or 0,
        valor_mercado=dados.get("valor_mercado", 0) or 0,
    )

    rule_of_40 = calcular_rule_of_40(
        crescimento_receita=crescimento_5a,
        margem_ebit=dados.get("marg_ebit", 0) or 0,
    )

    dcf_duas_fases = calcular_dcf_duas_fases(
        lucro_por_acao=lpa,
        crescimento_fase1=min(crescimento_5a, 0.30),
        anos_fase1=5,
        crescimento_fase2=0.04,
        taxa_desconto=taxa_desconto,
        preco_atual=preco,
    )

    crescimento_info = {
        "fase":          fase_crescimento,
        "crescimento_5a": round(crescimento_5a * 100, 1),
        "peg":           peg,
        "ev_receita":    ev_receita,
        "rule_of_40":    rule_of_40,
        "dcf_duas_fases": dcf_duas_fases,
    }

    # --- 5. MATRIZ DE CONSENSO DINÂMICA (MÉTODO AGREGADO) ---
    metodos_descontados = 0
    total_metodos_ativos = 0
    
    p_multiplos = multiplos.get("classificacao", "").strip().capitalize() if multiplos.get("classificacao") else "Não aplicável"
    p_ebitda    = ev_ebitda.get("classificacao", "").strip().capitalize() if ev_ebitda.get("classificacao") else "Não aplicável"
    p_dcf       = dcf.get("classificacao", "").strip().capitalize() if dcf.get("classificacao") else "Não aplicável"

    pilares = {
        "patrimonial_multiplos": p_multiplos,
        "operacional_ebitda":    p_ebitda,
        "fluxo_de_caixa":        p_dcf
    }
    
    for pilar, classif in pilares.items():
        if classif != "Não aplicável" and classif != "" and classif is not None:
            total_metodos_ativos += 1
            if classif == "Descontada":
                metodos_descontados += 1

    # Substitui o parecer dinâmico se a trava do score_cvm rebaixou o ativo
    if score_cvm_valor <= 3.0:
        parecer = score.get("parecer_analista", "")
    elif metodos_descontados == total_metodos_ativos and total_metodos_ativos > 0:
        parecer = "Alinhamento total de compra. Ativo descontado em todas as janelas de análise."
    elif metodos_descontados >= 1 and pilares["fluxo_de_caixa"] == "Cara":
        parecer = "Divergência estrutural. Operação barata no presente, mas pressionada por endividamento no longo prazo."
    elif pilares["fluxo_de_caixa"] == "Descontada" and pilares["operacional_ebitda"] == "Cara":
        parecer = "Ativo com projeção futura promissora, mas múltiplos operacionais atuais esticados."
    else:
        parecer = "Ativo em região de neutralidade. Preço de tela reflete de forma justa os fundamentos atuais."

    consenso_info = {
        "pilares_status": pilares,
        "grau_concordancia": score.get("grau_concordancia", f"{metodos_descontados}/{total_metodos_ativos} pilares descontados"),
        "parecer_analista": parecer
    }

    # Histórico e alertas contextuais
    historico = buscar_historico_5a(ticker_upper)
    alertas_historicos = gerar_alertas_historicos(historico, dcf, graham, bazin)

    # =========================================================================
    # CONSOLIDAÇÃO DO JSON FINAL E GERAÇÃO DOS DRIVERS
    # =========================================================================
    
    dados_finais = {
        "ticker":    ticker_upper,
        "nome":      dados.get("nome", ""),
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
            "industria":      subsetor,
            "metodos_validos": config_setor.get("metodos_validos", []),
            "metricas_ideais": config_setor.get("metricas_ideais", []),
        },
        "endividamento": endividamento,
        "capm":      capm,
        "ev_ebitda": ev_ebitda,
        "crescimento": crescimento_info,
        "consenso":  consenso_info,
        "saude_financeira": saude_financeira,
    }

    # Injeção da nova inteligência: Drivers de Valuation determinísticos
    dados_finais["drivers"] = gerar_drivers_valuation(dados_finais)

    return dados_finais


#DCF concessão: nova rota para empresas com concessões públicas, usando parâmetros específicos e lógica de detecção automática
def enriquecer_com_concessao(
    ticker: str,
    fcf_base: float,
    ativo_imob: float,
    divida_liq: float,
    num_acoes: float,
    wacc: float,
    resultado: dict,
    # Parâmetros opcionais vindos do frontend (sliders do usuário)
    prob_renovacao_override: Optional[float] = None,        # ✅
    desconto_pos_renovacao_override: Optional[float] = None, # ✅
) -> dict:
    """
    Enriquece o dicionário de resultado com a análise de concessão, se aplicável.
    Retorna o mesmo dicionário, modificado in-place.
    """
 
    params = detectar_concessao(ticker)
 
    if params is None:
        resultado["concessao"] = None
        return resultado
 
    # Permite o usuário ajustar os parâmetros via frontend (sliders)
    if prob_renovacao_override is not None:
        params.probabilidade_renovacao = prob_renovacao_override
    if desconto_pos_renovacao_override is not None:
        params.desconto_pos_renovacao = desconto_pos_renovacao_override
 
    # Usa o WACC já calculado pelo sistema (CAPM)
    params.wacc = wacc
 
    # Guarda FCF < 0 pode vir do CVM — protege o cálculo
    if fcf_base is None or fcf_base <= 0:
        resultado["concessao"] = {
            "aplicavel": False,
            "motivo": "FCF negativo ou indisponível — DCF concessão não calculado.",
            "ano_vencimento_principal": params.ano_vencimento_principal,
        }
        return resultado
 
    dcf_conc = calcular_dcf_concessao(
        fcf_base=fcf_base,
        ativo_imobilizado=ativo_imob,
        divida_liquida=divida_liq,
        numero_acoes=num_acoes,
        params=params,
    )
 
    resultado["concessao"] = {
        "aplicavel": True,
        "preco_justo": dcf_conc.preco_justo,
        "anos_ate_vencimento": dcf_conc.anos_ate_vencimento,
        "ano_vencimento_principal": params.ano_vencimento_principal,
        "ano_vencimento_secundario": params.ano_vencimento_secundario,
        "probabilidade_renovacao": dcf_conc.probabilidade_renovacao,
        "vp_fluxos_pre_cliff": dcf_conc.valor_presente_fluxos,
        "valor_terminal_esperado_pv": dcf_conc.valor_terminal_esperado_pv,
        "valor_terminal_renovacao": dcf_conc.valor_terminal_renovacao,
        "valor_terminal_liquidacao": dcf_conc.valor_terminal_liquidacao,
        "impacto_cliff_vs_perpetuidade": dcf_conc.impacto_cliff,
        "fluxos_projetados": dcf_conc.fluxos_projetados,
        "wacc_usado": dcf_conc.wacc_usado,
        "notas": dcf_conc.notas,
    }
 
    # Injeta o preço justo do DCF concessão também na lista de métodos
    # para participar do score de atratividade
    resultado["metodos"]["dcf_concessao"] = {
        "preco_justo": dcf_conc.preco_justo,
        "aplicavel": True,
        "descricao": f"DCF com cliff de concessão (2029/{params.ano_vencimento_secundario})",
        "notas": dcf_conc.notas,
    }
 
    return resultado


# ── NOVA ROTA DE INTELIGÊNCIA SETORIAL (PEER GROUP) ──

@app.get("/api/valuation/setor/concorrentes/{ticker}")
@app.get("/valuation/setor/concorrentes/{ticker}")
async def obter_concorrentes_setor_api(ticker: str, limit: int = 4):
    """
    Identifica os concorrentes diretos da empresa por subsetor e retorna
    uma lista resumida contendo múltiplos e scores para comparação direta.
    """
    ticker_upper = ticker.upper()
    
    try:
        dados_principal = buscar_dados(ticker_upper)
        if not dados_principal:
            raise HTTPException(status_code=404, detail="Ativo mestre não localizado.")
            
        subsetor = dados_principal.get("industria", "Geral")
        lista_concorrentes = buscar_concorrentes_por_subsetor(subsetor, ticker_upper)
        
        tickers_alvo = lista_concorrentes[:limit]
        resultado_concorrentes = []
        
        for t_concorrente in tickers_alvo:
            try:
                dados_c = buscar_dados(t_concorrente)
                if dados_c:
                    resultado_concorrentes.append({
                        "ticker": t_concorrente,
                        "nome": dados_c.get("nome", ""),
                        "preco_atual": dados_c.get("preco_atual", 0),
                        "pl": dados_c.get("pl", 0),
                        "pvp": dados_c.get("pvp", 0),
                        "ev_ebitda": dados_c.get("ev_ebitda", 0),
                        "dividend_yield": dados_c.get("dividend_yield", 0),
                    })
            except Exception:
                continue
                
        return {
            "ticker_referencia": ticker_upper,
            "subsetor_identificado": subsetor,
            "total_concorrentes_encontrados": len(lista_concorrentes),
            "concorrentes": resultado_concorrentes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno no agrupamento setorial: {str(e)}")


# ── Servir frontend estático em produção ────────────────────────────────────
# Montado DEPOIS de todas as rotas da API para não interceptá-las
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")