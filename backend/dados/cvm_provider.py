"""
cvm_provider.py
Otimizado: Cache em RAM para cadastro e demonstrações para máxima performance.
"""

import io
import os
import re
import logging
import requests
import pandas as pd
import unicodedata
from pathlib import Path

# Configuração de Logger
logger = logging.getLogger(__name__)
DADOS_DIR = Path(__file__).parent.parent / "dados_cvm"

# Contas IFRS
CONTA_RECEITA_LIQUIDA = "3.01"
CONTA_LUCRO_LIQUIDO   = "3.11"
CONTA_FCO             = "6.01"

# ─── CACHE GLOBAL EM MEMÓRIA ────────────────────────────────────────────────
_CADASTRO_CACHE = None
_DEMO_CACHE = {} # Estrutura: { 'tipo_cdcvm': pd.DataFrame }

def _normalizar_nome(nome: str) -> str:
    if not nome: return ""
    nome = "".join(c for c in unicodedata.normalize('NFD', nome) if unicodedata.category(c) != 'Mn')
    nome = nome.upper()
    sufixos = [r"\b(ON|PN|PNA|PNB|NM|N1|N2|N3|MB|MA|EJ|EB|DR3|PFD|PREFERENCIAL|ORDINARIA)\b", r"\bS\.?A\.?\b", r"\bS/A\b", r"\bCIA\.?\b", r"\bSA\b", r"\bLTDA\b"]
    for s in sufixos: nome = re.sub(s, "", nome, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", nome.replace("-", " ")).strip()

def _carregar_cadastro():
    global _CADASTRO_CACHE
    if _CADASTRO_CACHE is not None: return _CADASTRO_CACHE

    path = DADOS_DIR / "cad_cia_aberta.csv"
    if not path.exists():
        logger.error("Arquivo de cadastro não encontrado.")
        return pd.DataFrame()

    df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    df["CD_CVM"] = pd.to_numeric(df["CD_CVM"], errors="coerce")
    df["_NOME_NORM"] = df["DENOM_SOCIAL"].fillna("").apply(_normalizar_nome)
    df["_COMERC_NORM"] = df["DENOM_COMERC"].fillna("").apply(_normalizar_nome)
    _CADASTRO_CACHE = df
    return _CADASTRO_CACHE

def buscar_cd_cvm(nome_fundamentus: str):
    cadastro = _carregar_cadastro()
    if cadastro.empty: return None
    nome_norm = _normalizar_nome(nome_fundamentus)
    
    for col in ["_NOME_NORM", "_COMERC_NORM"]:
        m = cadastro[cadastro[col] == nome_norm]
        if not m.empty: return int(m.iloc[0]["CD_CVM"])
    
    return None

def _carregar_demo(tipo: str, cd_cvm: int) -> pd.DataFrame:
    """Carrega apenas uma vez para o cache global."""
    chave = f"{tipo}_{cd_cvm}"
    if chave in _DEMO_CACHE: return _DEMO_CACHE[chave]

    frames = []
    # Nota: Carregamos apenas o arquivo necessário para este CD_CVM se ele ainda não estiver no cache
    for path in DADOS_DIR.glob(f"{tipo}_*.csv"):
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
        df_emp = df[df["CD_CVM"].astype(str).str.zfill(6) == str(cd_cvm).zfill(6)]
        if not df_emp.empty: frames.append(df_emp)
    
    _DEMO_CACHE[chave] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return _DEMO_CACHE[chave]

def _extrair_serie(df: pd.DataFrame, codigo_conta: str) -> pd.Series:
    if df.empty: return pd.Series(dtype=float)
    mask = df["CD_CONTA"].str.startswith(codigo_conta)
    sub = df[mask].copy()
    if sub.empty: return pd.Series(dtype=float)
    sub["VL_NUM"] = pd.to_numeric(sub["VL_CONTA"], errors="coerce")
    sub["_FATOR"] = sub["ESCALA_MOEDA"].apply(lambda e: 1000.0 if str(e).strip().upper() == "MIL" else 1.0)
    sub["VL_NUM"] = sub["VL_NUM"] * sub["_FATOR"]
    sub["DT_FIM"] = pd.to_datetime(sub["DT_FIM_EXERC"], errors="coerce")
    return sub.groupby("DT_FIM")["VL_NUM"].sum().sort_index()
# ─── dicionário de tradução corporativa ───────────────────────────────────────

MAPA_NOMES_CVM = {
    # Âncoras de Blue Chips e casos complexos de strings
    "PETR4":  "PETROLEO BRASILEIRO S.A. - PETROBRAS",
    "PETR3":  "PETROLEO BRASILEIRO S.A. - PETROBRAS",
    
    # Casos Críticos e Rebrandings
    "WIZC3":  "WIZ CO PARTICIPAÇÕES E CORRETAGEM DE SEGUROS S.A.",
    "B3SA3":  "B3 S.A. - BRASIL, BOLSA, BALCÃO",
    "VIIA3":  "GRUPO CASAS BAHIA S.A.",
    "BHIA3":  "GRUPO CASAS BAHIA S.A.",
    "ALOS3":  "ALLOS S.A.", # Antiga Aliansce Sonae
    "PRIO3":  "PETRO RIO S.A.",
    
    # Energia e Saneamento (Nomes Longos)
    "TAEE3":  "TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S.A.",
    "TAEE4":  "TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S.A.",
    "TAEE11": "TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S.A.",
    "SAPR3":  "CIA SANEAMENTO DO PARANA SANEPAR",
    "SAPR4":  "CIA SANEAMENTO DO PARANA SANEPAR",
    "SAPR11": "CIA SANEAMENTO DO PARANA SANEPAR",
    "SBSP3":  "CIA SANEAMENTO BASICO EST SAO PAULO",
    "CMIG3":  "CIA ENERGETICA DE MINAS GERAIS - CEMIG",
    "CMIG4":  "CIA ENERGETICA DE MINAS GERAIS - CEMIG",
    "CPLE3":  "CIA PARANAENSE DE ENERGIA - COPEL",
    "CPLE6":  "CIA PARANAENSE DE ENERGIA - COPEL",
    "EQTL3":  "EQUATORIAL ENERGIA S.A.",

    # Bancos e Seguros
    "BBAS3":  "BANCO DO BRASIL S.A.",
    "BBSE3":  "BB SEGURIDADE PARTICIPACOES S.A.",
    "CXSE3":  "CAIXA SEGURIDADE PARTICIPACOES S.A.",
    "ITUB3":  "ITAU UNIBANCO HOLDING S.A.",
    "ITUB4":  "ITAU UNIBANCO HOLDING S.A.",
    "ITSA3":  "ITAUSA S.A.",
    "ITSA4":  "ITAUSA S.A.",

    # Varejo, Alimentos e Outros
    "MGLU3":  "MAGAZINE LUIZA S.A.",
    "RENT3":  "LOCALIZA RENT A CAR S.A.",
    "RAIL3":  "RUMO S.A.",
    "RDOR3":  "REDE D OR SAO LUIZ S.A.",
    "ABEV3":  "AMBEV S.A.",
    "ASAI3":  "SENDAS DISTRIBUIDORA S.A.", # Assaí Atacadista
    "CRFB3":  "ATACADAO S.A.",            # Grupo Carrefour
    "JBSS3":  "JBS S.A.",
    "BEEF3":  "MINERVA S.A.",
    "MRFG3":  "MARFRIG GLOBAL FOODS S.A.",
}

# ─── função principal ─────────────────────────────────────────────────────────

def buscar_saude_financeira_cvm(ticker: str, nome_empresa: str = "") -> dict:
    """Busca dados na CVM usando o mapeamento de ticker ou o nome oficial como fallback."""
    
    ticker_busca = ticker.upper().strip()
    
    # 1. VERIFICA O DICIONÁRIO PRIMEIRO
    if ticker_busca in MAPA_NOMES_CVM:
        razao_social_exata = MAPA_NOMES_CVM[ticker_busca]
        print(f"🔄 Traduzindo {ticker_busca} para a CVM: {razao_social_exata}")
    else:
        # Se não estiver no mapa das problemáticas, usa o nome real
        razao_social_exata = nome_empresa if nome_empresa else ticker_busca
        
    try:
        if not DADOS_DIR.exists() or not any(DADOS_DIR.iterdir()):
            return {
                "disponivel": False,
                "erro": "Dados CVM não encontrados. Execute backend/scripts/atualizar_cvm.py",
            }

        cd_cvm = buscar_cd_cvm(razao_social_exata)
        
        if cd_cvm is None:
            return {"disponivel": False, "erro": f"Empresa não encontrada na CVM: {razao_social_exata}"}

        logger.info(f"Carregando demonstrações CVM para CD_CVM={cd_cvm}")

        dre = _carregar_demo("itr_dre", cd_cvm)
        dfc = _carregar_demo("itr_dfc", cd_cvm)

        # complementa com DFP se ITR vazio
        if dre.empty:
            dre = _carregar_demo("dfp_dre", cd_cvm)
        if dfc.empty:
            dfc = _carregar_demo("dfp_dfc", cd_cvm)

        if dre.empty:
            return {"disponivel": False, "erro": "Demonstrações não disponíveis para este ticker", "cd_cvm": cd_cvm}

        receita = _extrair_serie(dre, CONTA_RECEITA_LIQUIDA)
        lucro   = _extrair_serie(dre, CONTA_LUCRO_LIQUIDO)
        fco     = _extrair_serie(dfc, CONTA_FCO)

        def serie_para_lista(s: pd.Series, n: int = 6) -> list:
            s = s.tail(n)
            result = []
            for dt, v in s.items():
                if pd.notna(v):
                    mes = dt.month
                    trimestre = (mes - 1) // 3 + 1
                    periodo = f"{dt.year}T{trimestre}"
                    result.append({"periodo": periodo, "valor": round(float(v) / 1_000_000, 1)})
            return result

        receita_lista = serie_para_lista(receita)
        lucro_lista   = serie_para_lista(lucro)
        fco_lista     = serie_para_lista(fco)

        margens = []
        r_vals = receita.tail(6).values
        l_vals = lucro.tail(6).values
        for r_v, l_v in zip(r_vals, l_vals):
            if r_v and r_v != 0:
                margens.append(round(float(l_v) / float(r_v) * 100, 1))

        tendencia_receita = "estável"
        if len(receita) >= 4:
            vals = receita.tail(4).values
            if float(vals[-1]) > float(vals[0]) * 1.05:
                tendencia_receita = "crescendo"
            elif float(vals[-1]) < float(vals[0]) * 0.95:
                tendencia_receita = "caindo"

        qualidade_lucro = None
        if not fco.empty and not lucro.empty and len(fco) >= 2 and len(lucro) >= 2:
            fco_sum   = float(fco.tail(4).sum())
            lucro_sum = float(lucro.tail(4).sum())
            if lucro_sum and lucro_sum != 0:
                qualidade_lucro = round(fco_sum / lucro_sum, 2)

        return {
            "disponivel": True,
            "cd_cvm": cd_cvm,
            "receita_trimestral": receita_lista,
            "lucro_trimestral": lucro_lista,
            "fco_trimestral": fco_lista,
            "margens_pct": margens,
            "tendencia_receita": tendencia_receita,
            "qualidade_lucro": qualidade_lucro,
        }

    except Exception as e:
        logger.error(f"Erro em buscar_saude_financeira_cvm: {e}")
        return {"disponivel": False, "erro": str(e)}