# backend/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from dados.provider import buscar_dados
from scanner.trabalhador import executar_scan, scan_em_andamento
from valuation.graham   import calcular_graham
from valuation.bazin    import calcular_bazin
from valuation.multiplos import calcular_multiplos
from valuation.dcf      import calcular_dcf
from valuation.score    import calcular_score, gerar_drivers_valuation
from valuation.risco import analisar_risco
from dados.historico import buscar_historico_5a, gerar_alertas_historicos
from valuation.setor import aplicar_restricoes_setor, buscar_concorrentes_por_subsetor
from valuation.endividamento import analisar_endividamento
from valuation.capm     import calcular_capm, resolver_beta
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
import json
from dados.cvm_provider import buscar_saude_financeira_cvm, buscar_capital_investido_proxy_cvm, buscar_crescimento_lucro_anual_cvm, buscar_ativos_para_liquidacao_cvm
from valuation.saude_financeira import calcular_saude_financeira, extrair_crescimento_cvm
from valuation.fcfe_valuation import calcular_valuation_fcfe
from dados.selic import buscar_selic_atual
from valuation.dcf_concessao import (
    calcular_dcf_concessao,
    detectar_concessao,
    empresa_tem_concessao,
    ParametrosConcessao,
)
from valuation.nopat import calcular_fcl_via_nopat
from cenarios_sensibilidade import (
    DeltasCenario,
    WaccInvalidoError,
    gerar_analise_completa,
)
from valor_liquidacao import calcular_valor_liquidacao
from sotp import Segmento, ConfiguracaoSotp, calcular_sotp, carregar_configuracao_sotp
from scorecard_qualitativo import ScorecardQualitativo, aplicar_ajuste_ao_score

app = FastAPI(
    title="Valuation Tracker API",
    description="API de análise fundamentalista de ações da B3",
    version="1.0.0",
)

# Setores cíclicos — limitar crescimento a 8% máximo. Nível de módulo (não
# mais inline dentro de valuation()) pra ser reaproveitado também pelo
# endpoint de Cenários/Sensibilidade sem duplicar o set literal uma 3ª vez
# (já existe uma cópia separada em scanner/trabalhador.py — ver CONTEXT.md
# sobre o bug de mismatch de string de setor corrigido nas duas cópias).
SETORES_CICLICOS = {
    "Transporte Aéreo", "Transporte",
    "Alimentos", "Mineração", "Siderurgia e Metalurgia",
}

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
#Api para analisar todas as empresas
@app.get("/api/scanner/resultado")
@app.get("/scanner/resultado")
def get_snapshot():
    caminho_arquivo = "dados/snapshot_mercado.json"
    
    # Verifica se o arquivo existe (caso o scanner ainda não tenha rodado)
    if not os.path.exists(caminho_arquivo):
        raise HTTPException(status_code=404, detail="Snapshot ainda não gerado. Aguarde o processamento.")
    
    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro ao ler os dados do mercado.")

@app.post("/api/scanner/disparar")
@app.post("/scanner/disparar")
def disparar_scan(background_tasks: BackgroundTasks):
    """Dispara a varredura da B3 em background. Ignora chamadas concorrentes."""
    if scan_em_andamento():
        return {"status": "ja_em_andamento"}
    background_tasks.add_task(executar_scan)
    return {"status": "varredura_iniciada"}

@app.get("/api/valuation/{ticker}")
@app.get("/valuation/{ticker}")
async def valuation(
    ticker: str,
    prob_renovacao: Optional[float] = None,
    desconto_pos_renovacao: Optional[float] = None,
):
    """
    Retorna o valuation completo de uma ação pelo ticker de forma 100% dinâmica.

    `prob_renovacao`/`desconto_pos_renovacao`: overrides opcionais do DCF
    Concessão (sliders do frontend) — só têm efeito quando o ticker é uma
    concessionária mapeada em valuation/dcf_concessao.py::CONCESSOES_CONHECIDAS.
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
    # Inicializado fora do try — se a chamada à CVM falhar, dados_cvm precisa
    # continuar definido (None) pro resto da função poder checar com segurança
    # (ex: pct_divida_moeda_estrangeira usado no WACC, ver abaixo).
    dados_cvm = None
    pct_divida_moeda_estrangeira = None

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
            pct_divida_moeda_estrangeira = dados_cvm.get("pct_divida_moeda_estrangeira")
    except Exception:
        saude_financeira = {"disponivel": False}
        crescimento_cvm = None

    # Usa dados CVM quando disponível (mais preciso que Fundamentus 5a)
    crescimento_historico = crescimento_cvm if crescimento_cvm is not None else (dados.get("crescimento_receita_5a", 0) or 0)
    # Limites de segurança: entre -5% e 15%
    taxa_crescimento = max(-0.05, min(crescimento_historico, 0.15))
    if taxa_crescimento == 0:
        taxa_crescimento = 0.05

    # Setores cíclicos — limitar crescimento a 8% máximo (SETORES_CICLICOS
    # agora é constante de módulo, ver topo do arquivo)
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
        beta_ativo=resolver_beta(dados.get("beta"), setor),
        valor_mercado=dados.get("valor_mercado", 0) or 0,
    )
    taxa_capm = capm.get("taxa_desconto", 0.12)

    # Ajuste extra para endividamento alto aplicado dinamicamente no WACC
    div_ebit = (dados.get("div_liquida", 0) or 0) / (dados.get("ebit_12m", 1) or 1)

    # --- CALCULO DO WACC DINÂMICO ---
    # calcular_wacc() lê dados.get("selic", 0.145) — sem injetar o Selic
    # real aqui, o Kd do WACC sempre usava o fallback fixo de 14,5%, nunca
    # o Selic buscado (selic_val) acima e já usado corretamente pro CAPM/Ke
    # umas linhas antes. Reaproveita o MESMO selic_val (não busca de novo)
    # pra CAPM e WACC nunca divergirem por causa de uma 2ª chamada com
    # cache expirado no meio da mesma requisição. Mesmo padrão já usado em
    # scanner/trabalhador.py. Ver CONTEXT.md.
    dados_wacc = dict(dados)
    dados_wacc["selic"] = selic_val
    taxa_desconto = calcular_wacc(dados_wacc, taxa_capm, pct_divida_moeda_estrangeira=pct_divida_moeda_estrangeira)

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
            divida_liquida=(dados.get("div_liquida", 0) or 0) / 1_000_000,
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

    # EV/EBITDA Híbrido (Blend 50/50 - Empresa vs Setor) — calculado ANTES de
    # aplicar_restricoes_setor() de propósito, pra poder passar o resultado
    # pra dentro dela e deixá-la sobrescrever com "Não aplicável" pra
    # setores que não usam EV/EBITDA (banco/seguradora — ver CONTEXT.md).
    # "ev_ebitda_setor" nunca foi uma chave real de config_setor (sempre
    # caía no default 8.0, com ou sem essa variável), então usar o literal
    # 8.0 aqui preserva o comportamento de antes sem depender de
    # config_setor, que só fica disponível depois da chamada abaixo.
    historico_ev = dados.get("ev_ebitda_medio_5a") or dados.get("ev_ebitda", 8.0)

    ev_ebitda = calcular_ev_ebitda(
        ev_ebitda_atual     = dados.get("ev_ebitda", 0) or 0,
        ev_ebitda_historico = historico_ev,
        ev_ebitda_setor     = 8.0,
        ebit_12m            = dados.get("ebit_12m", 0) or 0,
        num_acoes           = dados.get("num_acoes", 0) or 0,
        div_liquida         = dados.get("div_liquida", 0) or 0,
    )

    # Aplica restrições específicas por setor
    graham, bazin, multiplos, dcf, ev_ebitda, config_setor = aplicar_restricoes_setor(
        setor=setor,
        graham=graham,
        bazin=bazin,
        multiplos=multiplos,
        dcf=dcf,
        ev_ebitda=ev_ebitda,
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

    risco = analisar_risco(
        ticker=ticker_upper,
        setor=setor,
        score_atual=score.get("score", 0),
    )
    
    # Dívida Líquida/EBIT não se aplica a banco/seguradora — mesma razão de
    # Graham/DCF/EV-EBITDA (EBIT operacional não é um conceito limpo pra
    # esse tipo de negócio). Sem essa restrição, ebit_12m=0 caía no ramo
    # "else: div_ebit = 0" de analisar_endividamento(), mostrando "0,0x ·
    # sem alertas" — parece "sem dívida" quando na real é "métrica não se
    # aplica". config_setor já reflete a restrição de setor.py aqui (mesmo
    # objeto usado por aplicar_restricoes_setor() acima). O score que entra
    # tem que sair EXATAMENTE igual — sem crédito por "ausência de alerta"
    # nem penalização indevida (ver CONTEXT.md).
    if "endividamento" in config_setor.get("metodos_invalidos", []):
        endividamento = {
            "classificacao": "Não aplicável",
            "erro": config_setor.get("justificativas", {}).get("endividamento"),
            "div_liquida_ebit": None,
            "div_liquida_patrim": None,
            "alertas": [],
            "penalizacao": 0.0,
            "score_ajustado": score.get("score", 0),
        }
    else:
        endividamento = analisar_endividamento(
            div_liquida = dados.get("div_liquida", 0) or 0,
            ebit_12m    = dados.get("ebit_12m", 0) or 0,
            patrim_liq  = dados.get("patrim_liq", 0) or 0,
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

    # Crescimento de LUCRO (não de receita) pra projetar o LPA no DCF Duas
    # Fases — LPA é um fluxo pós-margem, crescer na taxa da receita ignora
    # compressão/expansão de margem no caminho (bug real, confirmado com
    # dado de mercado: BEEF3 teve CAGR de receita 5a de +23,1% contra CAGR
    # de lucro de só +0,4% no mesmo período — Status Invest). Fonte: CAGR
    # de lucro líquido anual via CVM (buscar_crescimento_lucro_anual_cvm),
    # só usado quando NENHUM exercício do período teve prejuízo (senão o
    # CAGR ponta-a-ponta esconde a volatilidade real, ver docstring da
    # função). Sem dado confiável -> piso conservador de 2%, nunca cai de
    # volta pro crescimento de receita (reintroduziria o próprio bug).
    crescimento_lucro_cvm = buscar_crescimento_lucro_anual_cvm(ticker_upper, dados.get("nome", ""))
    if crescimento_lucro_cvm.get("disponivel"):
        crescimento_lucro_fase1 = crescimento_lucro_cvm["cagr"]
    else:
        crescimento_lucro_fase1 = 0.02

    dcf_duas_fases = calcular_dcf_duas_fases(
        lucro_por_acao=lpa,
        crescimento_fase1=crescimento_lucro_fase1,
        anos_fase1=5,
        crescimento_fase2=0.04,
        # LPA já é fluxo de equity — desconta ao Ke (CAPM puro), não à WACC
        # (taxa_desconto), que subestimaria o custo de capital pra uma
        # empresa endividada e infla o valor justo. Bug real corrigido, ver
        # CONTEXT.md (quantificado pra BEEF3: +59,3% de inflação com WACC).
        ke=taxa_capm,
        preco_atual=preco,
    )

    # --- FCFE (equity DCF via CVM) — mesma premissa de crescimento do DCF
    # Duas Fases acima (crescimento_fase1/crescimento_fase2), pra os dois
    # valuations lado a lado serem comparáveis. Ke vem do CAPM (taxa_capm),
    # não da WACC (taxa_desconto) — o FCFE já é líquido dos efeitos de
    # dívida, desconta a custo de capital PRÓPRIO, não a WACC. Ver CONTEXT.md.
    fcfe = calcular_valuation_fcfe(
        ticker=ticker_upper,
        nome_empresa=dados.get("nome", ""),
        setor=setor,
        ke=taxa_capm,
        taxa_crescimento_explicito=min(crescimento_5a, 0.30),
        g_perpetuo=0.04,
        anos_explicitos=5,
        num_acoes=dados.get("num_acoes", 0) or 0,
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
        "fcfe": fcfe,
    }

    # Injeção da nova inteligência: Drivers de Valuation determinísticos
    dados_finais["drivers"] = gerar_drivers_valuation(dados_finais)

    # --- DCF Concessão (bug de wiring corrigido: enriquecer_com_concessao()
    # existia mas nunca era chamada — dados_finais["concessao"] nunca
    # aparecia na resposta real da API, então o card do frontend nunca
    # renderizava, mesmo pra tickers com concessão mapeada como GEPA4/GEPA3). ---
    if empresa_tem_concessao(ticker_upper):
        # Ativo Imobilizado líquido não é extraído em lugar nenhum hoje — a
        # CVM não baixa o BPA (lado do Ativo do balanço, ver CONTEXT.md), só
        # o BPP (Passivo + PL). Proxy em camadas, documentado — nunca trava
        # a feature por falta desse dado específico:
        #   1) CVM: Capital Investido = Dívida Bruta + Patrimônio Líquido
        #      (via buscar_capital_investido_proxy_cvm — pela identidade
        #      contábil Ativo=Passivo+PL, é uma superestimativa leve do
        #      Imobilizado pra uma concessionária asset-heavy, aceitável
        #      pro cenário conservador de liquidação do DCF Concessão);
        #   2) se a CVM não tiver dado utilizável pra esse ticker (achado
        #      real: GEPA4/Rio Paranapanema Energia reporta BPP e DRE
        #      inteiramente zerados desde 2024 — não é bug deste código,
        #      é o dado bruto da CVM pra essa empresa específica), cai pra
        #      EV via Fundamentus (valor de mercado + dívida líquida);
        #   3) se nem isso estiver disponível, usa 0.0 — o DCF Concessão
        #      ainda roda (cenário de liquidação fica conservador/nulo),
        #      não trava a feature inteira.
        capital_cvm = buscar_capital_investido_proxy_cvm(ticker_upper, dados.get("nome", ""))
        if capital_cvm.get("disponivel"):
            ativo_imob = capital_cvm["valor"] / 1_000_000
            origem_ativo_imob = "cvm"
        else:
            ev_fundamentus = (dados.get("valor_mercado", 0) or 0) + (dados.get("div_liquida", 0) or 0)
            if ev_fundamentus > 0:
                ativo_imob = ev_fundamentus / 1_000_000
                origem_ativo_imob = "ev_fundamentus"
            else:
                ativo_imob = 0.0
                origem_ativo_imob = "indisponivel"

        dados_finais = enriquecer_com_concessao(
            ticker=ticker_upper,
            fcf_base=fcl_ajustado,
            ativo_imob=ativo_imob,
            divida_liq=(dados.get("div_liquida", 0) or 0) / 1_000_000,
            num_acoes=dados.get("num_acoes", 0) or 0,
            wacc=taxa_desconto,
            resultado=dados_finais,
            prob_renovacao_override=prob_renovacao,
            desconto_pos_renovacao_override=desconto_pos_renovacao,
        )

        if dados_finais.get("concessao", {}).get("aplicavel") and origem_ativo_imob != "cvm":
            nota = (
                "⚠️ Ativo Imobilizado indisponível na CVM pra este ticker — "
                f"usado proxy via {'EV (valor de mercado + dívida líquida, Fundamentus)' if origem_ativo_imob == 'ev_fundamentus' else 'nenhum dado disponível (0)'}, "
                "não o valor de balanço real. Afeta só o cenário de não-renovação/liquidação."
            )
            dados_finais["concessao"].setdefault("notas", []).append(nota)

    return dados_finais


# ── Cenários e Análise de Sensibilidade (Fase 1 do roadmap de novas
# metodologias) ──────────────────────────────────────────────────────────
class DeltasCenarioBody(BaseModel):
    """
    Overrides opcionais dos deltas de cenário (pontos percentuais absolutos
    aplicados ao pessimista, com sinal invertido no otimista). Qualquer
    campo omitido/null usa o default de DeltasCenario — nunca hardcoded
    sem opção de override pelo chamador (ver cenarios_sensibilidade.py).
    """
    wacc_pp: Optional[float] = None
    g_perpetuo_pp: Optional[float] = None
    margem_ebitda_pp: Optional[float] = None
    crescimento_receita_pp: Optional[float] = None


def _preparar_deltas_cenario(body: Optional[DeltasCenarioBody]) -> Optional[DeltasCenario]:
    if body is None:
        return None
    padrao = DeltasCenario()
    return DeltasCenario(
        wacc_pp=body.wacc_pp if body.wacc_pp is not None else padrao.wacc_pp,
        g_perpetuo_pp=body.g_perpetuo_pp if body.g_perpetuo_pp is not None else padrao.g_perpetuo_pp,
        margem_ebitda_pp=body.margem_ebitda_pp if body.margem_ebitda_pp is not None else padrao.margem_ebitda_pp,
        crescimento_receita_pp=body.crescimento_receita_pp if body.crescimento_receita_pp is not None else padrao.crescimento_receita_pp,
    )


@app.post("/api/valuation/{ticker}/cenarios")
@app.post("/valuation/{ticker}/cenarios")
async def cenarios_e_sensibilidade(ticker: str, body: Optional[DeltasCenarioBody] = None):
    """
    Cenários (pessimista/base/otimista) e matriz de sensibilidade sobre o
    DCF principal — reaproveita calcular_dcf() via cenarios_sensibilidade.py
    (não duplica a lógica de projeção/desconto de fluxo de caixa), e as
    mesmas funções de WACC/CAPM/NOPAT já usadas em valuation() acima, pra
    chegar nos mesmos inputs base do DCF principal daquele ticker.

    Escopo desta preparação de inputs: deliberadamente NÃO chama a CVM
    (saúde financeira, crescimento de lucro) — usa crescimento de receita
    do Fundamentus (mesmo piso/teto/regra de setor cíclico já usados no
    DCF principal), o suficiente pra alimentar os 4 eixos de cenário/
    sensibilidade (WACC, g perpétuo, margem EBITDA, crescimento de
    receita) sem o custo/latência de rede extra da CVM, que não muda
    nenhum desses 4 inputs. Reaproveitar a preparação COMPLETA de
    valuation() (CVM incluída) fica como refactor futuro documentado em
    CONTEXT.md — não fazia parte do pedido desta fase.
    """
    ticker_upper = ticker.upper()

    try:
        dados = buscar_dados(ticker_upper)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar dados: {str(e)}")

    preco = dados.get("preco_atual", 0)
    acoes = (dados.get("num_acoes", 0) or 0) / 1_000_000
    setor = dados.get("setor", "Geral")

    fcl_ajustado = calcular_fcl_via_nopat(dados)
    if fcl_ajustado <= 0 or acoes <= 0:
        raise HTTPException(
            status_code=422,
            detail="DCF não aplicável para este ticker — fluxo de caixa insuficiente ou setor financeiro.",
        )

    # Mesma regra de crescimento (piso/teto + setor cíclico) do DCF
    # principal em valuation() — sem o crescimento_receita_5a via CVM
    # (ver docstring acima).
    crescimento_5a = dados.get("crescimento_receita_5a", 0) or 0
    taxa_crescimento = max(-0.05, min(crescimento_5a, 0.15))
    if taxa_crescimento == 0:
        taxa_crescimento = 0.05
    if setor in SETORES_CICLICOS:
        taxa_crescimento = min(taxa_crescimento, 0.08)
    lpa = dados.get("lpa", 0) or 0
    vpa = dados.get("vpa", 0) or 0
    if taxa_crescimento < 0 and lpa > 0 and vpa > 0:
        taxa_crescimento = 0.02

    # Mesmo padrão de wiring de Selic->WACC de valuation() (ver
    # test_wacc_wiring.py): calcular_wacc() nunca pode receber o dict
    # `dados` bruto sem "selic" injetado a partir da MESMA variável usada
    # no CAPM, senão cai no fallback hardcoded de 14,5%.
    selic_val = buscar_selic_atual()
    capm = calcular_capm(
        setor=setor,
        selic_atual=selic_val,
        beta_ativo=resolver_beta(dados.get("beta"), setor),
        valor_mercado=dados.get("valor_mercado", 0) or 0,
    )
    taxa_capm = capm.get("taxa_desconto", 0.12)
    dados_wacc = dict(dados)
    dados_wacc["selic"] = selic_val
    taxa_desconto = calcular_wacc(dados_wacc, taxa_capm)

    margem_ebitda_atual = dados.get("marg_ebit", 0) or 0
    divida_liquida = (dados.get("div_liquida", 0) or 0) / 1_000_000

    deltas = _preparar_deltas_cenario(body)

    try:
        resultado = gerar_analise_completa(
            fluxo_caixa_atual=fcl_ajustado,
            taxa_crescimento=taxa_crescimento,
            taxa_desconto=taxa_desconto,
            anos_projecao=5,
            taxa_crescimento_perpetuidade=0.03,
            num_acoes=acoes,
            preco_atual=preco,
            margem_ebitda_atual=margem_ebitda_atual,
            divida_liquida=divida_liquida,
            deltas=deltas,
        )
    except WaccInvalidoError as e:
        raise HTTPException(status_code=422, detail=str(e))

    resultado["ticker"] = ticker_upper
    resultado["nome"] = dados.get("nome", "")
    return resultado


# ── Valor de Liquidação (Fase 2 do roadmap de novas metodologias) ───────────
@app.get("/api/valuation/{ticker}/liquidacao")
@app.get("/valuation/{ticker}/liquidacao")
async def valor_liquidacao_endpoint(ticker: str, contingencias: Optional[float] = None):
    """
    Piso conservador de valor via balanço patrimonial (Ativo por classe +
    Passivo Total, ambos via CVM/BPA+BPP — ver
    dados/cvm_provider.py::buscar_ativos_para_liquidacao_cvm() e
    valuation_liquidacao.py::calcular_valor_liquidacao()).

    `contingencias`: query param opcional (mesma unidade de R$ absolutos
    dos demais valores) — a CVM não disponibiliza uma estimativa
    estruturada de contingências, então esse campo só é aplicado quando o
    chamador informa explicitamente (ver docstring de
    calcular_valor_liquidacao).

    Ao contrário do endpoint de Cenários (que sempre retorna um cálculo ou
    422 em caso de input matematicamente inválido), aqui a ausência de
    dado da CVM é um estado NORMAL/esperado pra parte dos tickers (mesmo
    padrão de `saude_financeira`/`fcfe` no payload principal) — devolve
    200 com `disponivel: False`, não 404/422, pro frontend tratar como
    "indisponível" e não como erro.
    """
    ticker_upper = ticker.upper()

    try:
        dados = buscar_dados(ticker_upper)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar dados: {str(e)}")

    ativos = buscar_ativos_para_liquidacao_cvm(ticker_upper, dados.get("nome", ""))
    if not ativos.get("disponivel"):
        return {
            "ticker": ticker_upper,
            "nome": dados.get("nome", ""),
            "disponivel": False,
            "erro": ativos.get("erro", "Dados de balanço indisponíveis via CVM para este ticker."),
        }

    resultado = calcular_valor_liquidacao(
        caixa_equivalentes=ativos["caixa_equivalentes"],
        aplicacoes_financeiras=ativos["aplicacoes_financeiras"],
        contas_a_receber=ativos["contas_a_receber"],
        estoques=ativos["estoques"],
        imobilizado=ativos["imobilizado"],
        intangivel=ativos["intangivel"],
        passivo_total=ativos["passivo_total"],
        num_acoes=dados.get("num_acoes", 0) or 0,
        contingencias=contingencias,
    )

    # Transparência de cobertura: soma BRUTA (pré-haircut) das 6 classes
    # cobertas vs. Ativo Total real do BPA — deixa explícito que este NÃO é
    # o Ativo Total (deliberado, ver docstring de
    # buscar_ativos_para_liquidacao_cvm), sem esconder quanto ficou de fora.
    soma_bruta_classes = (
        ativos["caixa_equivalentes"] + ativos["aplicacoes_financeiras"] + ativos["contas_a_receber"]
        + ativos["estoques"] + ativos["imobilizado"] + ativos["intangivel"]
    )
    resultado["ticker"] = ticker_upper
    resultado["nome"] = dados.get("nome", "")
    resultado["disponivel"] = True
    resultado["ativo_total_bpa"] = round(ativos["ativo_total_bpa"], 2)
    resultado["cobertura_ativo_total_pct"] = (
        round(soma_bruta_classes / ativos["ativo_total_bpa"] * 100, 1) if ativos["ativo_total_bpa"] > 0 else None
    )
    return resultado


# ── SOTP — Soma das Partes (Fase 3 do roadmap de novas metodologias) ───────
class SegmentoBody(BaseModel):
    nome: str
    metodo: str  # "ev_ebitda" | "ev_receita" | "dcf"
    ebitda: Optional[float] = None
    multiplo_ev_ebitda: Optional[float] = None
    receita: Optional[float] = None
    multiplo_ev_receita: Optional[float] = None
    fluxo_caixa_atual: Optional[float] = None
    taxa_crescimento: Optional[float] = None
    taxa_desconto: Optional[float] = None
    anos_projecao: Optional[int] = None
    taxa_crescimento_perpetuidade: Optional[float] = None


class ConfiguracaoSotpBody(BaseModel):
    segmentos: List[SegmentoBody]
    divida_liquida_consolidada: float = 0.0
    num_acoes: float = 0.0
    desconto_holding_pct: float = 0.0


@app.post("/api/valuation/{ticker}/sotp")
@app.post("/valuation/{ticker}/sotp")
async def sotp_endpoint(ticker: str, body: Optional[ConfiguracaoSotpBody] = None):
    """
    Valuation por Soma das Partes (SOTP) — cada segmento avaliado
    separadamente (ver sotp.py::calcular_ev_segmento()), somados e
    ajustados por dívida líquida consolidada + desconto de holding.

    A configuração de segmentos pode vir no corpo da requisição (`body`,
    útil pra simular cenários ad-hoc sem editar arquivo) — quando omitida,
    carrega de `dados/sotp_config.json` (configuração manual por ticker,
    ver sotp.py::carregar_configuracao_sotp()). Sem configuração em
    nenhum dos dois lugares, devolve 200 com `disponivel: False` (mesmo
    padrão de `saude_financeira`/liquidação — ausência de configuração
    manual é um estado normal pra maioria dos tickers, não um erro).
    """
    ticker_upper = ticker.upper()

    if body is not None:
        config = ConfiguracaoSotp(
            segmentos=[Segmento(**segmento.model_dump()) for segmento in body.segmentos],
            divida_liquida_consolidada=body.divida_liquida_consolidada,
            num_acoes=body.num_acoes,
            desconto_holding_pct=body.desconto_holding_pct,
        )
    else:
        config = carregar_configuracao_sotp(ticker_upper)
        if config is None:
            return {
                "ticker": ticker_upper,
                "disponivel": False,
                "erro": (
                    "Nenhuma configuração de segmentos encontrada para este ticker. "
                    "Envie a configuração no corpo da requisição ou adicione-a em dados/sotp_config.json."
                ),
            }

    resultado = calcular_sotp(config)
    resultado["ticker"] = ticker_upper
    resultado["disponivel"] = True
    return resultado


# ── Scorecard Qualitativo (Fase 4 do roadmap de novas metodologias) ────────
class ScorecardBody(BaseModel):
    """
    `score_base`: o Score de Atratividade REAL daquele ticker (0-10),
    vindo do payload já retornado por GET /api/valuation/{ticker}
    (`resultado.score.score`) — este endpoint não refaz a coleta de dados/
    CVM/WACC/CAPM pra recalcular o score do zero (evita duplicar todo o
    pipeline pesado de valuation() só pra isso); o frontend já tem esse
    número na tela quando o usuário mexe nos sliders do scorecard, então
    é ele quem envia. Isso é o que garante que o ajuste NUNCA fica
    desconectado do resto do app — ele sempre parte do score real
    calculado pra aquele ticker naquela consulta, nunca de um valor
    inventado à parte.

    As 5 dimensões usam os defaults de ScorecardQualitativo (5.0, neutro)
    quando omitidas.
    """
    score_base: float
    moat: float = 5.0
    gestao: float = 5.0
    concentracao_clientes: float = 5.0
    risco_regulatorio: float = 5.0
    poder_precificacao: float = 5.0


@app.post("/api/valuation/{ticker}/scorecard")
@app.post("/valuation/{ticker}/scorecard")
async def scorecard_qualitativo_endpoint(ticker: str, body: ScorecardBody):
    """
    Converte o Scorecard Qualitativo (5 sliders 0-10) num ajuste aditivo
    e limitado (ver scorecard_qualitativo.py::TETO_AJUSTE_PONTOS) aplicado
    ao Score de Atratividade já calculado pro ticker.

    Endpoint sem estado/persistência: a persistência do scorecard entre
    sessões é feita no FRONTEND via localStorage, mesmo mecanismo já
    usado pela Watchlist (ver App.tsx::WATCHLIST_KEY) — o projeto ainda
    não migrou nenhum dado de usuário pra armazenamento server-side (Fase
    3 do roadmap principal, "Supabase + Auth", ainda não iniciada, ver
    CONTEXT.md), então introduzir persistência server-side só pro
    scorecard, isoladamente, seria inconsistente com o resto do app e
    antecipar uma decisão de arquitetura maior sem necessidade. Este
    endpoint só CALCULA o ajuste — não salva nada em disco/banco.
    """
    try:
        scorecard = ScorecardQualitativo(
            moat=body.moat,
            gestao=body.gestao,
            concentracao_clientes=body.concentracao_clientes,
            risco_regulatorio=body.risco_regulatorio,
            poder_precificacao=body.poder_precificacao,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    resultado = aplicar_ajuste_ao_score(score_base=body.score_base, scorecard=scorecard)
    resultado["ticker"] = ticker.upper()
    return resultado


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

    # Preço justo <= 0 é matematicamente válido (o cálculo rodou — não é
    # indisponibilidade de dado), mas é um sinal forte de inconsistência
    # nos inputs (ex: dívida líquida muito acima do valor de empresa
    # projetado, o que aconteceu de fato com GEPA4: CVM reporta o
    # balanço/DRE zerados desde 2024 pra esse ticker especificamente — ver
    # CONTEXT.md). Não escondemos o número (é informação real de que algo
    # está errado na fonte), só marcamos explicitamente como não confiável
    # em vez de deixar aparecer cru no frontend como se fosse um
    # preço-alvo normal.
    if dcf_conc.preco_justo is not None and dcf_conc.preco_justo <= 0:
        resultado["concessao"]["confiabilidade_baixa"] = True
        resultado["concessao"]["notas"].append(
            "⚠️ Preço justo negativo ou nulo — indica inconsistência nos dados de entrada "
            "(ex: balanço/DRE zerados na fonte), não deve ser usado como referência de valor."
        )
 
    # Injeta o preço justo do DCF concessão também na lista de métodos
    # para participar do score de atratividade. `resultado["metodos"]`
    # nunca é inicializado por quem chama esta função (dados_finais em
    # main.py::valuation() não tem essa chave) — setdefault defensivo pra
    # não estourar KeyError quando a concessão é de fato aplicável.
    resultado.setdefault("metodos", {})["dcf_concessao"] = {
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