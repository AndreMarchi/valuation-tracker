# backend/valuation/setor.py
import fundamentus
import pandas as pd
import os
import json

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
        "metodos_invalidos": ["graham", "dcf"],
        "justificativas": {
            "graham": "Graham não se aplica a bancos — VPA inclui carteira de crédito, distorcendo o resultado.",
            "dcf":    "DCF clássico não se aplica a bancos — lucro líquido não equivale a fluxo de caixa livre.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Dividend Yield", "ROE"],
    },
    "Bancos": {
        "metodos_validos":   ["bazin", "pl", "pvp"],
        "metodos_invalidos": ["graham", "dcf"],
        "justificativas": {
            "graham": "Graham não se aplica a bancos.",
            "dcf":    "DCF clássico não se aplica a bancos.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Dividend Yield", "ROE"],
    },
    "Seguradoras": {
        "metodos_validos":   ["bazin", "pl", "pvp"],
        "metodos_invalidos": ["graham", "dcf"],
        "justificativas": {
            "graham": "Graham não se aplica a seguradoras.",
            "dcf":    "DCF não se aplica a seguradoras.",
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


def get_configuracao_setor(setor: str, ticker: str = "") -> dict:
    if ticker.upper() in TICKERS_HOLDINGS:
        return {
            "metodos_validos":   ["pvp", "bazin"],
            "metodos_invalidos": ["graham", "pl", "dcf"],
            "justificativas": {
                "graham": "Graham não se aplica a holdings.",
                "pl":      "P/L distorcido em holdings — lucro vem de equivalência patrimonial.",
                "dcf":     "DCF não se aplica a holdings.",
            },
            "metricas_ideais": ["P/VP", "Dividend Yield", "Desconto sobre NAV"],
        }

    if setor in CONFIGURACAO_SETORES:
        return CONFIGURACAO_SETORES[setor]

    setor_lower = setor.lower()
    for chave, config in CONFIGURACAO_SETORES.items():
        if chave.lower() in setor_lower or setor_lower in chave.lower():
            return config

    return CONFIGURACAO_PADRAO


def aplicar_restricoes_setor(setor: str, graham: dict, bazin: dict, multiplos: dict, dcf: dict, ticker: str = "") -> tuple:
    config = get_configuracao_setor(setor, ticker)
    invalidos = config["metodos_invalidos"]
    justificativas = config["justificativas"]

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
    if "dcf" in invalidos:
        dcf = {**dcf, "classificacao": "Não aplicável", "erro": justificativas.get("dcf"), "valor_intrinseco": None}

    return graham, bazin, multiplos, dcf, config


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

    # Identifica o ativo atual no JSON
    empresa_atual = None
    for emp in BASE_EMPRESAS_JSON:
        tickers_empresa = [t.strip() for t in str(emp.get("Tickets", "")).upper().split(",")]
        if ticker_atual_upper in tickers_empresa:
            empresa_atual = emp
            break

    alvo_segmento = empresa_atual.get("Segmento_de_mercado") if empresa_atual else subsetor_alvo
    alvo_setor = empresa_atual.get("Setor_de_atuacao") if empresa_atual else ""

    # Varre os candidatos do JSON
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

    # Junta todos os candidatos em uma lista única (sem duplicatas)
    todos_candidatos = list(dict.fromkeys(concorrentes_exatos + concorrentes_setor))
    
    if not todos_candidatos:
        return ["PETR4", "VALE3", "ITUB4", "WEGE3"]

    # ====================================================================
    # MOTOR DE RANQUEAMENTO (Os 3 Critérios de Corte)
    # ====================================================================
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
        
        # Captura os dados financeiros
        liquidez = float(dados.get('liq2m', 0))
        patrimonio = float(dados.get('patrliq', 0))
        pvp = float(dados.get('pvp', 1))
        pl_concorrente = float(dados.get('pl', 0))
        
        # Valor de Mercado aproximado (Patrimônio Líquido * P/VP)
        valor_mercado = patrimonio * pvp if pvp > 0 else patrimonio
        # Distância de Múltiplo (Quão parecido é o P/L)
        distancia_pl = abs(pl_concorrente - pl_mestre)

        lista_ranqueada.append({
            "ticker": ticker,
            "liquidez": liquidez,
            "valor_mercado": valor_mercado,
            "distancia_pl": distancia_pl
        })

    # Critério 1: Elimina empresas que negociam menos de R$ 500 mil/dia (Garante liquidez)
    candidatos_liquidos = [c for c in lista_ranqueada if c['liquidez'] > 500000]
    if len(candidatos_liquidos) >= 3:
        lista_ranqueada = candidatos_liquidos

    # Critério 2: Ordena pelos gigantes (Maiores Valores de Mercado)
    lista_ranqueada.sort(key=lambda x: x['valor_mercado'], reverse=True)
    top_10_maiores = lista_ranqueada[:10]

    # Critério 3: Entre os 10 gigantes, escolhe os 6 com múltiplos mais parecidos com o nosso ativo
    top_10_maiores.sort(key=lambda x: x['distancia_pl'])

    top_6_finais = [c['ticker'] for c in top_10_maiores[:6]]
    
    return top_6_finais if top_6_finais else todos_candidatos[:6]