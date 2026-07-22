# backend/valuation/setor.py
import fundamentus
import pandas as pd
import os
import json

from valuation.multiplos import classificacao_agregada_multiplos

# ============================================================================
# 1. CARREGAMENTO DA BASE JSON LOCAL
# ============================================================================

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
CAMINHO_JSON = os.path.join(DIRETORIO_ATUAL, "..", "dados", "setores_b3.json")

def carregar_base_setores():
    """Carrega a base estrutural de empresas da B3 diretamente da memória."""
    try:
        with open(CAMINHO_JSON, 'r', encoding='utf-8') as arquivo:
            return json.load(arquivo)
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível carregar o JSON de setores: {e}")
        return []

# Carrega os dados uma única vez quando o servidor iniciar
BASE_EMPRESAS_JSON = carregar_base_setores()


# ============================================================================
# 2. MAPAS DE CONFIGURAÇÃO ESTÁTICA (RESTRIÇÕES E PESOS)
# ============================================================================

CONFIGURACAO_SETORES = {
    "Intermediários Financeiros": {
        "metodos_validos":   ["bazin", "pl", "pvp"],
        "metodos_invalidos": ["graham", "dcf", "ev_ebitda", "endividamento"],
        "justificativas": {
            "graham": "Graham não se aplica a bancos — VPA inclui carteira de crédito, distorcendo o resultado.",
            "dcf":    "DCF clássico não se aplica a bancos — lucro líquido não equivale a fluxo de caixa livre.",
            "ev_ebitda": "EV/EBITDA não se aplica a bancos — EBITDA não é uma métrica operacional limpa quando juros são o núcleo da receita/despesa, e Enterprise Value pressupõe separar dívida financeira de operação, o que não existe pra esse tipo de negócio.",
            "endividamento": "Dívida Líquida/EBIT não se aplica a bancos — o EBIT operacional não é um conceito limpo pra esse tipo de negócio (mesma razão de Graham/DCF/EV-EBITDA), então a métrica de alavancagem baseada nele não é confiável.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Dividend Yield", "ROE"],
    },
    "Bancos": {
        "metodos_validos":   ["bazin", "pl", "pvp"],
        "metodos_invalidos": ["graham", "dcf", "ev_ebitda", "endividamento"],
        "justificativas": {
            "graham": "Graham não se aplica a bancos.",
            "dcf":    "DCF clássico não se aplica a bancos.",
            "ev_ebitda": "EV/EBITDA não se aplica a bancos — EBITDA não é uma métrica operacional limpa quando juros são o núcleo da receita/despesa, e Enterprise Value pressupõe separar dívida financeira de operação, o que não existe pra esse tipo de negócio.",
            "endividamento": "Dívida Líquida/EBIT não se aplica a bancos — o EBIT operacional não é um conceito limpo pra esse tipo de negócio (mesma razão de Graham/DCF/EV-EBITDA), então a métrica de alavancagem baseada nele não é confiável.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Dividend Yield", "ROE"],
    },
    "Seguradoras": {
        "metodos_validos":   ["bazin", "pl", "pvp"],
        "metodos_invalidos": ["graham", "dcf", "ev_ebitda", "endividamento"],
        "justificativas": {
            "graham": "Graham não se aplica a seguradoras.",
            "dcf":    "DCF não se aplica a seguradoras.",
            "ev_ebitda": "EV/EBITDA não se aplica a seguradoras — pela mesma razão dos bancos: EBITDA não é uma métrica operacional limpa e Enterprise Value pressupõe separar dívida financeira de operação, o que não existe pra esse tipo de negócio.",
            "endividamento": "Dívida Líquida/EBIT não se aplica a seguradoras — pela mesma razão dos bancos: o EBIT operacional não é um conceito limpo pra esse tipo de negócio.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Combined Ratio", "ROE"],
    },
    "Energia Elétrica": {
        "metodos_validos":   ["graham", "bazin", "pl", "pvp"],
        "metodos_invalidos": ["dcf"],
        "justificativas": {
            "dcf": "DCF distorcido pelo alto capex regulatório do setor elétrico.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Dividend Yield", "EV/EBITDA"],
    },
    "Varejo": {
        "metodos_validos":   ["graham", "pl", "pvp", "dcf"],
        "metodos_invalidos": ["bazin"],
        "justificativas": {
            "bazin": "Empresas de varejo geralmente reinvestem lucros e pagam poucos dividendos.",
        },
        "metricas_ideais": ["P/L", "EV/EBITDA", "Margem Líquida", "DCF"],
    },
    "Construção Civil": {
        "metodos_validos":   ["graham", "pl", "pvp", "dcf"],
        "metodos_invalidos": ["bazin"],
        "justificativas": {
            "bazin": "Construtoras geralmente não pagam dividendos regulares.",
        },
        "metricas_ideais": ["P/L", "P/VP", "VSO", "Margem Bruta"],
    },
}

TICKERS_HOLDINGS = {
    "ITSA3", "ITSA4", "EGIE3", "CSAN3", "RDOR3", 
    "BRGE3", "BRGE11", "LREN3", "SFRA3", "BPAC11",
}

CONFIGURACAO_PADRAO = {
    "metodos_validos":   ["graham", "bazin", "pl", "pvp", "dcf"],
    "metodos_invalidos": [],
    "justificativas":    {},
    "metricas_ideais":   ["Graham", "Bazin", "P/L", "P/VP", "DCF"],
}

MAPA_PESOS_SETORIAIS = [
    {
        "termos": ["bancos", "seguros", "financeiros", "saúde"],
        "pesos": {"graham": 0.4, "bazin": 0.3, "pl": 0.15, "pvp": 0.15, "dcf": 0.0}
    },
    {
        "termos": ["energia", "água", "saneamento", "elétrica"],
        "pesos": {"graham": 0.1, "bazin": 0.4, "pl": 0.1, "pvp": 0.1, "dcf": 0.3}
    },
    {
        "termos": ["vestuário", "comércio", "tecnologia", "varejo"],
        "pesos": {"graham": 0.0, "bazin": 0.1, "pl": 0.3, "pvp": 0.1, "dcf": 0.5}
    }
]

PESOS_PADRAO = {"graham": 0.2, "bazin": 0.2, "pl": 0.2, "pvp": 0.2, "dcf": 0.2}


# ============================================================================
# 3. LÓGICA DE EXECUÇÃO
# ============================================================================

def obter_todos_resultados_fundamentus() -> pd.DataFrame:
    try:
        return fundamentus.get_resultado()
    except Exception:
        return pd.DataFrame()


def get_configuracao_setor(nome_setor: str, ticker: str = "") -> dict:
    """Retorna o dicionário de regras do setor garantindo todas as chaves obrigatórias."""
    setor_limpo = str(nome_setor).lower().strip()
    ticker_upper = str(ticker).upper().strip()
    
    # Inicializa uma cópia limpa do modelo padrão para evitar mutabilidade cruzada
    config = {
        "metodos_validos": list(CONFIGURACAO_PADRAO["metodos_validos"]),
        "metodos_invalidos": list(CONFIGURACAO_PADRAO["metodos_invalidos"]),
        "justificativas": dict(CONFIGURACAO_PADRAO["justificativas"]),
        "metricas_ideais": list(CONFIGURACAO_PADRAO["metricas_ideais"])
    }

    # 1. Varre o mapa estático global por correspondência parcial de strings
    # Guard pra setor_limpo vazio: string vazia é substring de qualquer coisa
    # em Python ("" in "bancos" é True), então sem esse guard um setor
    # vazio/ausente casaria incorretamente com a primeira chave do dict
    # (mesma vulnerabilidade encontrada e corrigida em
    # fcfe_valuation.py::eh_setor_bancario_ou_segurador() — ver CONTEXT.md).
    encontrou_setor = False
    if setor_limpo:
        for chave, dados in CONFIGURACAO_SETORES.items():
            if chave.lower() in setor_limpo or setor_limpo in chave.lower():
                config.update({
                    "metodos_validos": list(dados.get("metodos_validos", [])),
                    "metodos_invalidos": list(dados.get("metodos_invalidos", [])),
                    "justificativas": dict(dados.get("justificativas", {})),
                    "metricas_ideais": list(dados.get("metricas_ideais", []))
                })
                encontrou_setor = True
                break

    # 2. Fallbacks dinâmicos para correspondências parciais exigidas pelos testes
    if not encontrou_setor:
        if "tecnologia" in setor_limpo:
            config.update({
                "metodos_validos": ["pl", "dcf"],
                "metodos_invalidos": ["graham", "bazin", "pvp"],
                "justificativas": {
                    "graham": "Graham invalido para empresas de crescimento tecnológico.",
                    "bazin": "Empresas de tecnologia priorizam reinvestimento a dividendos.",
                    "pvp": "P/VP distorcido por ativos intangíveis de tecnologia."
                },
                "metricas_ideais": ["EV/EBITDA", "Crescimento de Receita", "Margem EBIT"]
            })
        elif "petróleo" in setor_limpo or "gas" in setor_limpo or "gás" in setor_limpo:
            config.update({
                "metodos_validos": ["graham", "bazin", "pl", "pvp", "ev_ebitda"],
                "metodos_invalidos": [],
                "justificativas": {},
                "metricas_ideais": ["Graham", "Bazin", "P/L", "P/VP", "DCF", "EV/EBITDA"]
            })

    # 3. REGRA DE SOBREPOSIÇÃO (OVERRIDE) PARA HOLDINGS
    if ticker_upper in TICKERS_HOLDINGS:
        invalidos_holding = ["graham", "pl", "dcf"]
        
        for inv in invalidos_holding:
            if inv not in config["metodos_invalidos"]:
                config["metodos_invalidos"].append(inv)
            if inv in config["metodos_validos"]:
                config["metodos_validos"].remove(inv)
                
        config["justificativas"]["graham"] = "Graham não se aplica a holdings devido à dupla contagem."
        config["justificativas"]["pl"] = "P/L sofre distorção contábil por equivalência patrimonial."
        config["justificativas"]["dcf"] = "DCF não se aplica diretamente ao fluxo de uma holding."

    return config


def aplicar_restricoes_setor(setor: str, graham: dict, bazin: dict, multiplos: dict, dcf: dict, ev_ebitda: dict = None, ticker: str = "") -> tuple:
    # Correção da assinatura da chamada interna adicionando o parâmetro opcional 'ticker'
    config = get_configuracao_setor(setor, ticker)
    invalidos = config.get("metodos_invalidos", [])
    justificativas = config.get("justificativas", {})

    if "graham" in invalidos:
        graham = {**graham, "classificacao": "Não aplicável", "erro": justificativas.get("graham"), "preco_justo": None}
    if "bazin" in invalidos:
        bazin = {**bazin, "classificacao": "Não aplicável", "erro": justificativas.get("bazin"), "preco_justo": None}
    if "pl" in invalidos:
        multiplos["pl"]["classificacao"] = "Não aplicável"
        multiplos["pl"]["erro"] = justificativas.get("pl")
    if "pvp" in invalidos:
        multiplos["pvp"]["classificacao"] = "Não aplicável"
        multiplos["pvp"]["erro"] = justificativas.get("pvp")
    if "pl" in invalidos or "pvp" in invalidos:
        # Recalcula a classificação agregada (usada pelo pilar
        # "patrimonial_multiplos" da Matriz de Consenso) — se não recalcular
        # aqui, ela fica presa ao valor calculado ANTES da restrição de
        # setor zerar pl/pvp (ex: setor "Tecnologia" invalida P/VP), ficando
        # desatualizada em relação ao que os sub-campos pl/pvp mostram.
        multiplos["classificacao"] = classificacao_agregada_multiplos(
            multiplos["pl"]["classificacao"], multiplos["pvp"]["classificacao"]
        )
    if "dcf" in invalidos:
        dcf = {**dcf, "classificacao": "Não aplicável", "erro": justificativas.get("dcf"), "valor_intrinseco": None}
    if "ev_ebitda" in invalidos and ev_ebitda is not None:
        ev_ebitda = {**ev_ebitda, "classificacao": "Não aplicável", "erro": justificativas.get("ev_ebitda"), "preco_justo": None}

    return graham, bazin, multiplos, dcf, ev_ebitda, config


def obter_pesos_setoriais(subsetor: str) -> dict:
    subsetor_norm = str(subsetor).lower()
    for categoria in MAPA_PESOS_SETORIAIS:
        if any(termo in subsetor_norm for termo in categoria["termos"]):
            return categoria["pesos"]
    return PESOS_PADRAO


# ── BUSCA DE CONCORRENTES VIA JSON ──

def buscar_concorrentes_por_subsetor(subsetor_alvo: str, ticker_atual: str) -> list:
    """
    Busca concorrentes no JSON local e aplica 3 filtros institucionais:
    1. Liquidez Mínima (> 500k/dia)
    2. Tamanho (Maior Valor de Mercado)
    3. Proximidade (Ciclo e precificação via P/L)
    """
    ticker_atual_upper = ticker_atual.upper().strip()
    concorrentes_exatos = []
    concorrentes_setor = []

    if not BASE_EMPRESAS_JSON:
        return ["PETR4", "VALE3", "ITUB4", "WEGE3"]

    empresa_atual = None
    for emp in BASE_EMPRESAS_JSON:
        tickers_empresa = [t.strip() for t in str(emp.get("Tickets", "")).upper().split(",")]
        if ticker_atual_upper in tickers_empresa:
            empresa_atual = emp
            break

    alvo_segmento = empresa_atual.get("Segmento_de_mercado") if empresa_atual else subsetor_alvo
    alvo_setor = empresa_atual.get("Setor_de_atuacao") if empresa_atual else ""

    for emp in BASE_EMPRESAS_JSON:
        tickers_raw = str(emp.get("Tickets", "")).upper()
        if not tickers_raw or tickers_raw == "NONE":
            continue
            
        tickers_empresa = [t.strip() for t in tickers_raw.split(",")]
        if ticker_atual_upper in tickers_empresa:
            continue

        ticker_principal = tickers_empresa[0]

        if alvo_segmento and emp.get("Segmento_de_mercado") == alvo_segmento:
            concorrentes_exatos.append(ticker_principal)
        elif alvo_setor and emp.get("Setor_de_atuacao") == alvo_setor:
            concorrentes_setor.append(ticker_principal)

    todos_candidatos = list(dict.fromkeys(concorrentes_exatos + concorrentes_setor))
    
    if not todos_candidatos:
        return ["PETR4", "VALE3", "ITUB4", "WEGE3"]

    df_resultado = obter_todos_resultados_fundamentus()
    if df_resultado.empty:
        return todos_candidatos[:6]

    dados_mestre = df_resultado.loc[ticker_atual_upper] if ticker_atual_upper in df_resultado.index else None
    pl_mestre = float(dados_mestre.get('pl', 0)) if dados_mestre is not None else 0

    lista_ranqueada = []

    for ticker in todos_candidatos:
        if ticker not in df_resultado.index:
            continue
            
        dados = df_resultado.loc[ticker]
        
        liquidez = float(dados.get('liq2m', 0))
        patrimonio = float(dados.get('patrliq', 0))
        pvp = float(dados.get('pvp', 1))
        pl_concorrente = float(dados.get('pl', 0))
        
        valor_mercado = patrimonio * pvp if pvp > 0 else patrimonio
        distancia_pl = abs(pl_concorrente - pl_mestre)

        lista_ranqueada.append({
            "ticker": ticker,
            "liquidez": liquidez,
            "valor_mercado": valor_mercado,
            "distancia_pl": distancia_pl
        })

    candidatos_liquidos = [c for c in lista_ranqueada if c['liquidez'] > 500000]
    if len(candidatos_liquidos) >= 3:
        lista_ranqueada = candidatos_liquidos

    lista_ranqueada.sort(key=lambda x: x['valor_mercado'], reverse=True)
    top_10_maiores = lista_ranqueada[:10]

    top_10_maiores.sort(key=lambda x: x['distancia_pl'])

    top_6_finais = [c['ticker'] for c in top_10_maiores[:6]]
    
    return top_6_finais if top_6_finais else todos_candidatos[:6]