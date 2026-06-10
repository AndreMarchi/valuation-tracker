# backend/valuation/setor.py
import fundamentus
import pandas as pd

# Mapeamento original de setores para métodos válidos e inválidos
CONFIGURACAO_SETORES = {
    # ── Financeiro ────────────────────────────────────────────
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
            "graham": "Graham não se aplica a bancos — VPA inclui carteira de crédito, distorcendo o resultado.",
            "dcf":    "DCF clássico não se aplica a bancos — lucro líquido não equivale a fluxo de caixa livre.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Dividend Yield", "ROE"],
    },
    "Seguradoras": {
        "metodos_validos":   ["bazin", "pl", "pvp"],
        "metodos_invalidos": ["graham", "dcf"],
        "justificativas": {
            "graham": "Graham não se aplica a seguradoras — estrutura de capital muito diferente.",
            "dcf":    "DCF clássico não se aplica a seguradoras — fluxo de caixa tem natureza distinta.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Combined Ratio", "ROE"],
    },

    # ── Energia ───────────────────────────────────────────────
    "Energia Elétrica": {
        "metodos_validos":   ["graham", "bazin", "pl", "pvp"],
        "metodos_invalidos": ["dcf"],
        "justificativas": {
            "dcf": "DCF distorcido pelo alto capex regulatório do setor elétrico.",
        },
        "metricas_ideais": ["P/L", "P/VP", "Dividend Yield", "EV/EBITDA"],
    },
    "Petróleo, Gás e Biocombustíveis": {
        "metodos_validos":   ["bazin", "pl", "pvp", "dcf"],
        "metodos_invalidos": ["graham"],
        "justificativas": {
            "graham": "Graham não captura o valor das reservas de petróleo não contabilizadas no patrimônio.",
        },
        "metricas_ideais": ["EV/EBITDA", "P/L", "Dividend Yield", "DCF"],
    },

    # ── Construção e Real Estate ───────────────────────────────
    "Construção Civil": {
        "metodos_validos":   ["graham", "pl", "pvp", "dcf"],
        "metodos_invalidos": ["bazin"],
        "justificativas": {
            "bazin": "Construtoras geralmente não pagam dividendos regulares — Bazin não se aplica.",
        },
        "metricas_ideais": ["P/L", "P/VP", "VSO", "Margem Bruta"],
    },
    "Fundos Imobiliários": {
        "metodos_validos":   ["bazin", "pvp"],
        "metodos_invalidos": ["graham", "pl", "dcf"],
        "justificativas": {
            "graham": "Graham não se aplica a FIIs — estrutura de fundo sem LPA tradicional.",
            "pl":      "P/L não é métrica relevante para FIIs — usar P/VP and Dividend Yield.",
            "dcf":     "DCF não se aplica a FIIs — usar Cap Rate and Dividend Yield.",
        },
        "metricas_ideais": ["Dividend Yield", "P/VP", "Cap Rate"],
    },

    # ── Varejo ────────────────────────────────────────────────
    "Varejo": {
        "metodos_validos":   ["graham", "pl", "pvp", "dcf"],
        "metodos_invalidos": ["bazin"],
        "justificativas": {
            "bazin": "Empresas de varejo geralmente reinvestem lucros e pagam poucos dividendos.",
        },
        "metricas_ideais": ["P/L", "EV/EBITDA", "Margem Líquida", "DCF"],
    },

    # ── Tecnologia ────────────────────────────────────────────
    "Tecnologia": {
        "metodos_validos":   ["pl", "dcf"],
        "metodos_invalidos": ["graham", "bazin", "pvp"],
        "justificativas": {
            "graham": "Graham não se aplica a tech — empresas de alto crescimento têm VPA baixo.",
            "bazin":  "Empresas de tecnologia raramente pagam dividendos — Bazin não se aplica.",
            "pvp":    "P/VP não é relevante para tech — valor está nos ativos intangíveis.",
        },
        "metricas_ideais": ["P/L", "EV/Receita", "DCF", "Crescimento de Receita"],
    },

    # ── Agronegócio ───────────────────────────────────────────
    "Agronegócio": {
        "metodos_validos":   ["pl", "pvp", "dcf"],
        "metodos_invalidos": ["graham", "bazin"],
        "justificativas": {
            "graham": "Graham distorcido pela sazonalidade dos ativos agrícolas.",
            "bazin":  "Dividendos do agronegócio são irregulares — Bazin não se aplica bem.",
        },
        "metricas_ideais": ["EV/EBITDA", "P/L", "DCF"],
    },
    "Holdings": {
        "metodos_validos":   ["pvp", "bazin"],
        "metodos_invalidos": ["graham", "pl", "dcf"],
        "justificativas": {
            "graham": "Graham não se aplica a holdings — patrimônio é composto de participações em outras empresas.",
            "pl":      "P/L distorcido em holdings — lucro vem de equivalência patrimonial, não de operações.",
            "dcf":     "DCF não se aplica a holdings — não há fluxo de caixa operacional próprio.",
        },
        "metricas_ideais": ["P/VP", "Dividend Yield", "Desconto sobre NAV"],
    },
    "Participações": {
        "metodos_validos":   ["pvp", "bazin"],
        "metodos_invalidos": ["graham", "pl", "dcf"],
        "justificativas": {
            "graham": "Graham não se aplica a holdings — patrimônio é composto de participações em outras empresas.",
            "pl":      "P/L distorcido — lucro vem de equivalência patrimonial.",
            "dcf":     "DCF não se aplica — não há fluxo de caixa operacional próprio.",
        },
        "metricas_ideais": ["P/VP", "Dividend Yield", "Desconto sobre NAV"],
    },
    "Transporte Aéreo": {
        "metodos_validos":   ["pl", "pvp", "dcf"],
        "metodos_invalidos": ["graham", "bazin"],
        "justificativas": {
            "graham": "Graham não se aplica a aéreas — VPA frequentemente negativo por arrendamento de aeronaves.",
            "bazin":  "Empresas aéreas raramente pagam dividendos — Bazin não se aplica.",
        },
        "metricas_ideais": ["EV/EBITDA", "P/L", "DCF", "Dívida Líquida/EBITDA"],
    },
    "Transporte": {
        "metodos_validos":   ["pl", "pvp", "dcf", "bazin"],
        "metodos_invalidos": ["graham"],
        "justificativas": {
            "graham": "Setor de transporte tem ativos físicos intensivos que distorcem o VPA.",
        },
        "metricas_ideais": ["EV/EBITDA", "P/L", "DCF"],
    },
}

TICKERS_HOLDINGS = {
    "ITSA3", "ITSA4",
    "EGIE3",
    "CSAN3",
    "RDOR3",
    "BRGE3", "BRGE11",
    "LREN3",
    "SFRA3",
    "BPAC11",
}

CONFIGURACAO_PADRAO = {
    "metodos_validos":   ["graham", "bazin", "pl", "pvp", "dcf"],
    "metodos_invalidos": [],
    "justificativas":    {},
    "metricas_ideais":   ["Graham", "Bazin", "P/L", "P/VP", "DCF"],
}


def get_configuracao_setor(setor: str, ticker: str = "") -> dict:
    if ticker.upper() in TICKERS_HOLDINGS:
        return {
            "metodos_validos":   ["pvp", "bazin"],
            "metodos_invalidos": ["graham", "pl", "dcf"],
            "justificativas": {
                "graham": "Graham não se aplica a holdings — patrimônio é composto de participações em outras empresas.",
                "pl":      "P/L distorcido em holdings — lucro vem de equivalência patrimonial.",
                "dcf":     "DCF não se aplica a holdings — não há fluxo de caixa operacional próprio.",
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


def aplicar_restricoes_setor(
    setor: str,
    graham: dict,
    bazin: dict,
    multiplos: dict,
    dcf: dict,
    ticker: str = "",
) -> tuple:
    config = get_configuracao_setor(setor, ticker)
    invalidos = config["metodos_invalidos"]
    justificativas = config["justificativas"]

    if "graham" in invalidos:
        graham = {
            **graham,
            "classificacao": "Não aplicável",
            "erro": justificativas.get("graham", "Não aplicável para este setor"),
            "preco_justo": None,
            "margem_seguranca": None,
        }

    if "bazin" in invalidos:
        bazin = {
            **bazin,
            "classificacao": "Não aplicável",
            "erro": justificativas.get("bazin", "Não aplicável para este setor"),
            "preco_justo": None,
            "margem_seguranca": None,
        }

    if "pl" in invalidos:
        multiplos = {
            **multiplos,
            "pl": {
                **multiplos["pl"],
                "classificacao": "Não aplicável",
                "desconto": None,
                "erro": justificativas.get("pl", "Não aplicável para este setor"),
            }
        }

    if "pvp" in invalidos:
        multiplos = {
            **multiplos,
            "pvp": {
                **multiplos["pvp"],
                "classificacao": "Não aplicável",
                "desconto": None,
                "erro": justificativas.get("pvp", "Não aplicável para este setor"),
            }
        }

    if "dcf" in invalidos:
        dcf = {
            **dcf,
            "classificacao": "Não aplicável",
            "erro": justificativas.get("dcf", "Não aplicável para este setor"),
            "valor_intrinseco": None,
            "margem_seguranca": None,
            "cenarios": None,
        }

    return graham, bazin, multiplos, dcf, config


# ── NOVAS IMPLEMENTAÇÕES DE INTELIGÊNCIA SETORIAL DINÂMICA ──

def obter_todos_resultados_fundamentus() -> pd.DataFrame:
    try:
        return fundamentus.get_resultado()
    except Exception:
        return pd.DataFrame()


def buscar_concorrentes_por_subsetor(subsetor_alvo: str, ticker_atual: str) -> list:
    if not subsetor_alvo or subsetor_alvo == "Geral":
        return []
    ticker_atual_upper = ticker_atual.upper()
    try:
        df_detalhes = fundamentus.get_detalhes_geral()
        if df_detalhes.empty:
            return []
        df_filtrado = df_detalhes[df_detalhes['Subsetor'].str.upper() == subsetor_alvo.upper()]
        return [str(t).upper() for t in df_filtrado.index if str(t).upper() != ticker_atual_upper]
    except Exception:
        return []


def obter_pesos_setoriais(subsetor: str) -> dict:
    subsetor_norm = str(subsetor).lower()
    
    # 1. Setores Financeiros
    if "bancos" in subsetor_norm or "seguros" in subsetor_norm or "financeiros" in subsetor_norm:
        return {"graham": 0.4, "bazin": 0.3, "pl": 0.15, "pvp": 0.15, "dcf": 0.0}
    
    # 2. Setores Altamente Predictíveis (Energia, Saneamento)
    if "energia" in subsetor_norm or "água" in subsetor_norm or "saneamento" in subsetor_norm:
        return {"graham": 0.1, "bazin": 0.4, "pl": 0.1, "pvp": 0.1, "dcf": 0.3}
    
    # 3. Setores de Crescimento / Varejo Cíclico
    if "vestuário" in subsetor_norm or "comércio" in subsetor_norm or "tecnologia" in subsetor_norm:
        return {"graham": 0.0, "bazin": 0.1, "pl": 0.3, "pvp": 0.1, "dcf": 0.5}
        
    return {"graham": 0.2, "bazin": 0.2, "pl": 0.2, "pvp": 0.2, "dcf": 0.2}