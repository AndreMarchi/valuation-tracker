"""
cvm_provider.py
Lê demonstrações financeiras trimestrais da CVM a partir de arquivos
em disco (backend/dados_cvm/), gerados pelo script atualizar_cvm.py.
Fallback para download direto quando rodando localmente.
"""

import io
import os
import re
import logging
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── diretório de dados ───────────────────────────────────────────────────────

DADOS_DIR = Path(__file__).parent.parent / "dados_cvm"

# ─── contas CVM (padrão IFRS) ─────────────────────────────────────────────────

CONTA_RECEITA_LIQUIDA = "3.01"
CONTA_LUCRO_LIQUIDO   = "3.11"
CONTA_FCO             = "6.01"

# ─── normalização de nomes ───────────────────────────────────────────────────

def _normalizar_nome(nome: str) -> str:
    sufixos = [
        r"\b(ON|PN|PNA|PNB|NM|N1|N2|N3|MB|MA|EJ|EB|DR3)\b",
        r"\bS\.?A\.?\b", r"\bS/A\b", r"\bCIA\.?\b",
        r"\bSA\b", r"\bLTDA\b",
    ]
    nome = nome.upper()
    for s in sufixos:
        nome = re.sub(s, "", nome, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", nome).strip()

# ─── cadastro → CD_CVM ───────────────────────────────────────────────────────

_cadastro_cache = None

def _carregar_cadastro():
    global _cadastro_cache
    if _cadastro_cache is not None:
        return _cadastro_cache

    path = DADOS_DIR / "cad_cia_aberta.csv"

    if path.exists():
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    else:
        # fallback: tenta baixar direto (só funciona localmente)
        logger.info("Arquivo de cadastro não encontrado em disco — tentando download...")
        try:
            r = requests.get(
                "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv",
                timeout=20
            )
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.content.decode("latin-1")), sep=";", dtype=str)
            df = df[df["SIT"] == "ATIVO"].copy()
            DADOS_DIR.mkdir(exist_ok=True)
            df.to_csv(path, sep=";", index=False, encoding="utf-8")
        except Exception as e:
            logger.error(f"Não foi possível carregar o cadastro CVM: {e}")
            return pd.DataFrame()

    df["CD_CVM"] = pd.to_numeric(df["CD_CVM"], errors="coerce")
    df["_NOME_NORM"]   = df["DENOM_SOCIAL"].fillna("").apply(_normalizar_nome)
    df["_COMERC_NORM"] = df["DENOM_COMERC"].fillna("").apply(_normalizar_nome)
    _cadastro_cache = df
    logger.info(f"Cadastro CVM carregado: {len(df)} empresas")
    return df


def buscar_cd_cvm(nome_fundamentus: str):
    try:
        cadastro = _carregar_cadastro()
        if cadastro.empty:
            return None

        nome_norm = _normalizar_nome(nome_fundamentus)

        # 1. exato pelo nome social
        m = cadastro[cadastro["_NOME_NORM"] == nome_norm]
        if not m.empty:
            return int(m.iloc[0]["CD_CVM"])

        # 2. exato pelo nome comercial
        m = cadastro[cadastro["_COMERC_NORM"] == nome_norm]
        if not m.empty:
            return int(m.iloc[0]["CD_CVM"])

        # 3. parcial pela primeira palavra ≥4 chars
        palavras = [p for p in nome_norm.split() if len(p) >= 4]
        if palavras:
            kw = palavras[0]
            m = cadastro[
                cadastro["_NOME_NORM"].str.contains(kw, na=False) |
                cadastro["_COMERC_NORM"].str.contains(kw, na=False)
            ]
            if not m.empty:
                return int(m.iloc[0]["CD_CVM"])

        logger.warning(f"CD_CVM não encontrado para: '{nome_fundamentus}'")
        return None
    except Exception as e:
        logger.error(f"Erro em buscar_cd_cvm: {e}")
        return None

# ─── leitura de demonstrações do disco ───────────────────────────────────────

def _carregar_demo(tipo: str, cd_cvm: int) -> pd.DataFrame:
    """
    Carrega e filtra demonstrações do tipo especificado (ex: 'itr_dre').
    Concatena todos os anos disponíveis em disco.
    """
    frames = []
    for path in sorted(DADOS_DIR.glob(f"{tipo}_*.csv")):
        try:
            df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
            df_emp = df[df["CD_CVM"].astype(str).str.zfill(6) == str(cd_cvm).zfill(6)]
            if not df_emp.empty:
                frames.append(df_emp)
        except Exception as e:
            logger.warning(f"Erro ao ler {path.name}: {e}")

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _extrair_serie(df: pd.DataFrame, codigo_conta: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    mask = df["CD_CONTA"].str.startswith(codigo_conta)
    sub = df[mask].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    sub["VL_NUM"] = pd.to_numeric(sub["VL_CONTA"], errors="coerce")
    # respeita escala: MIL = valores em milhares, UNIDADE = valores em reais
    sub["_FATOR"] = sub["ESCALA_MOEDA"].apply(lambda e: 1000.0 if str(e).strip().upper() == "MIL" else 1.0)
    sub["VL_NUM"] = sub["VL_NUM"] * sub["_FATOR"]  # converte tudo para R$ reais
    sub["DT_FIM"] = pd.to_datetime(sub["DT_FIM_EXERC"], errors="coerce")
    return sub.groupby("DT_FIM")["VL_NUM"].sum().sort_index()

# ─── função principal ─────────────────────────────────────────────────────────
MAPA_NOMES_CVM = {
    "WIZC3": "WIZ CO PARTICIPAÇÕES E CORRETAGEM DE SEGUROS S.A.",
    "B3SA3": "B3 S.A. - BRASIL, BOLSA, BALCÃO",
    "BBAS3": "BANCO DO BRASIL S.A.",
    "MGLU3": "MAGAZINE LUIZA S.A.",
    "VIIA3": "GRUPO CASAS BAHIA S.A.",
    "BHIA3": "GRUPO CASAS BAHIA S.A.",
}

# ─── função principal ─────────────────────────────────────────────────────────

def buscar_saude_financeira_cvm(nome_ou_ticker: str) -> dict:
    """Busca dados na CVM usando o nome oficial ou mapeamento direto de ticker."""
    
    termo_busca = nome_ou_ticker.upper().strip()
    
    # 1. VERIFICA O DICIONÁRIO PRIMEIRO
    # Se receber o ticker "WIZC3", substitui pelo nome oficial exigido no cadastro da CVM
    if termo_busca in MAPA_NOMES_CVM:
        razao_social_exata = MAPA_NOMES_CVM[termo_busca]
        print(f"🔄 Traduzindo {termo_busca} para a CVM: {razao_social_exata}")
    else:
        razao_social_exata = termo_busca
        
    try:
        if not DADOS_DIR.exists() or not any(DADOS_DIR.iterdir()):
            return {
                "disponivel": False,
                "erro": "Dados CVM não encontrados. Execute backend/scripts/atualizar_cvm.py",
            }

        # CORREÇÃO: Agora passamos a razão social já traduzida para o buscador de códigos
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